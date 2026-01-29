#!/usr/bin/env python3
"""Digiman Monitor - Separate menu bar app for tracking automations."""

import rumps
import webbrowser
import json
import threading
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template_string, jsonify

# Configuration
STATUS_FILE = Path.home() / ".digiman" / "cron_status.json"
MONITOR_PORT = 5051
PROJECT_DIR = Path(__file__).parent.parent

# Flask app for dashboard
flask_app = Flask(__name__)

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Digiman Monitor</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/lucide@latest/dist/umd/lucide.min.js"></script>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
        .pulse { animation: pulse 2s infinite; }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
    </style>
</head>
<body class="bg-gray-900 text-white min-h-screen">
    <div class="max-w-4xl mx-auto p-6" x-data="monitorApp()" x-init="loadStatus(); setInterval(() => loadStatus(), 10000)">
        <!-- Header -->
        <div class="flex items-center justify-between mb-8">
            <div class="flex items-center gap-4">
                <div class="w-12 h-12 bg-gradient-to-br from-yellow-400 to-orange-500 rounded-xl flex items-center justify-center text-2xl">
                    ⚡
                </div>
                <div>
                    <h1 class="text-2xl font-bold">Digiman Monitor</h1>
                    <p class="text-gray-400 text-sm">Automation Status Dashboard</p>
                </div>
            </div>
            <div class="flex items-center gap-3">
                <span class="text-xs text-gray-500">Auto-refresh: 10s</span>
                <button @click="runAllJobs()"
                        :disabled="isRunning"
                        class="px-4 py-2 bg-yellow-500 text-black rounded-lg font-medium hover:bg-yellow-400 transition-colors disabled:opacity-50 flex items-center gap-2">
                    <span x-show="!isRunning">▶ Run All</span>
                    <span x-show="isRunning" class="pulse">Running...</span>
                </button>
            </div>
        </div>

        <!-- Status Cards -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
            <!-- Overall Status -->
            <div class="bg-gray-800 rounded-xl p-5 border border-gray-700">
                <div class="flex items-center gap-3 mb-4">
                    <div class="w-10 h-10 rounded-lg flex items-center justify-center"
                         :class="status.all_healthy ? 'bg-green-500/20' : 'bg-red-500/20'">
                        <i :data-lucide="status.all_healthy ? 'check-circle' : 'alert-circle'"
                           class="w-5 h-5"
                           :class="status.all_healthy ? 'text-green-400' : 'text-red-400'"></i>
                    </div>
                    <span class="text-gray-400 text-sm font-medium">System Status</span>
                </div>
                <div class="text-3xl font-bold" :class="status.all_healthy ? 'text-green-400' : 'text-red-400'"
                     x-text="status.all_healthy ? 'Healthy' : 'Issues'"></div>
            </div>

            <!-- Last Sync -->
            <div class="bg-gray-800 rounded-xl p-5 border border-gray-700">
                <div class="flex items-center gap-3 mb-4">
                    <div class="w-10 h-10 bg-blue-500/20 rounded-lg flex items-center justify-center">
                        <i data-lucide="clock" class="w-5 h-5 text-blue-400"></i>
                    </div>
                    <span class="text-gray-400 text-sm font-medium">Last Sync</span>
                </div>
                <div class="text-2xl font-bold text-white" x-text="status.last_sync_ago || 'Never'"></div>
                <div class="text-xs text-gray-500 mt-1" x-text="status.last_sync || ''"></div>
            </div>

            <!-- Items Today -->
            <div class="bg-gray-800 rounded-xl p-5 border border-gray-700">
                <div class="flex items-center gap-3 mb-4">
                    <div class="w-10 h-10 bg-purple-500/20 rounded-lg flex items-center justify-center">
                        <i data-lucide="zap" class="w-5 h-5 text-purple-400"></i>
                    </div>
                    <span class="text-gray-400 text-sm font-medium">Items Today</span>
                </div>
                <div class="text-3xl font-bold text-white" x-text="status.items_today || 0"></div>
            </div>
        </div>

        <!-- Upcoming Schedule -->
        <div class="bg-gray-800 rounded-xl border border-gray-700 p-5 mb-8">
            <div class="flex items-center gap-3 mb-4">
                <div class="w-10 h-10 bg-orange-500/20 rounded-lg flex items-center justify-center">
                    <i data-lucide="calendar-clock" class="w-5 h-5 text-orange-400"></i>
                </div>
                <h2 class="font-bold text-lg">Upcoming Schedule</h2>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div class="flex items-center gap-3 p-3 bg-gray-700/50 rounded-lg">
                    <span class="text-2xl">📝</span>
                    <div>
                        <div class="text-sm text-gray-400">Nightly Sync</div>
                        <div class="font-medium" x-text="status.next_nightly_sync || 'Not scheduled'"></div>
                    </div>
                </div>
                <div class="flex items-center gap-3 p-3 bg-gray-700/50 rounded-lg">
                    <span class="text-2xl">🌅</span>
                    <div>
                        <div class="text-sm text-gray-400">Morning Push</div>
                        <div class="font-medium" x-text="status.next_morning_push || 'Not scheduled'"></div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Jobs -->
        <div class="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden mb-8">
            <div class="p-4 border-b border-gray-700">
                <h2 class="font-bold text-lg">Automation Jobs</h2>
            </div>
            <div class="divide-y divide-gray-700">
                <template x-for="job in status.jobs" :key="job.name">
                    <div class="p-4 flex items-center justify-between hover:bg-gray-750">
                        <div class="flex items-center gap-4">
                            <div class="w-10 h-10 rounded-lg flex items-center justify-center"
                                 :class="job.status === 'success' ? 'bg-green-500/20' : (job.status === 'error' ? 'bg-red-500/20' : 'bg-gray-700')">
                                <span x-text="job.icon" class="text-xl"></span>
                            </div>
                            <div>
                                <div class="font-medium" x-text="job.name"></div>
                                <div class="text-sm text-gray-400" x-text="job.description"></div>
                            </div>
                        </div>
                        <div class="flex items-center gap-4">
                            <div class="text-right">
                                <div class="text-sm"
                                     :class="job.status === 'success' ? 'text-green-400' : (job.status === 'error' ? 'text-red-400' : 'text-gray-500')"
                                     x-text="job.status === 'success' ? '✓ Success' : (job.status === 'error' ? '✗ Failed' : 'Not run')"></div>
                                <div class="text-xs text-gray-500" x-text="job.last_run || 'Never'"></div>
                            </div>
                            <button @click="runJob(job.id)"
                                    :disabled="job.running"
                                    class="px-3 py-1.5 bg-gray-700 rounded-lg text-sm hover:bg-gray-600 transition-colors disabled:opacity-50">
                                <span x-show="!job.running">Run</span>
                                <span x-show="job.running" class="pulse">...</span>
                            </button>
                        </div>
                    </div>
                </template>
            </div>
        </div>

        <!-- History -->
        <div class="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
            <div class="p-4 border-b border-gray-700">
                <h2 class="font-bold text-lg">Recent Activity</h2>
            </div>
            <div class="divide-y divide-gray-700 max-h-96 overflow-y-auto">
                <template x-for="entry in status.history" :key="entry.timestamp">
                    <div class="p-3 flex items-center gap-3 text-sm">
                        <div class="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0"
                             :class="entry.status === 'success' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'">
                            <span x-text="entry.status === 'success' ? '✓' : '✗'" class="text-xs"></span>
                        </div>
                        <div class="flex-1 min-w-0">
                            <span class="text-gray-300" x-text="entry.source || 'Manual'"></span>
                            <span class="text-gray-500">·</span>
                            <span class="text-gray-400" x-text="entry.count + ' items'"></span>
                        </div>
                        <div class="text-gray-500 text-xs" x-text="entry.timestamp?.substring(0, 16).replace('T', ' ')"></div>
                    </div>
                </template>
                <div x-show="!status.history?.length" class="p-8 text-center text-gray-500">
                    No activity yet. Click "Run All" to start syncing.
                </div>
            </div>
        </div>

        <!-- Toast -->
        <div x-show="toast" x-transition
             class="fixed bottom-4 right-4 px-4 py-3 rounded-lg shadow-lg bg-gray-700 text-white">
            <span x-text="toast"></span>
        </div>
    </div>

    <script src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js" defer></script>
    <script>
        function monitorApp() {
            return {
                status: {
                    all_healthy: true,
                    last_sync: null,
                    last_sync_ago: 'Never',
                    items_today: 0,
                    jobs: [
                        { id: 'granola', name: 'Granola Sync', description: 'Extract action items from meetings', icon: '📝', status: 'pending', last_run: null, running: false },
                        { id: 'slack', name: 'Slack Sync', description: 'Import @mentions as todos', icon: '💬', status: 'pending', last_run: null, running: false },
                        { id: 'morning_push', name: 'Morning Push', description: 'Send daily todos to Slack', icon: '🌅', status: 'pending', last_run: null, running: false }
                    ],
                    history: []
                },
                isRunning: false,
                toast: null,

                async loadStatus() {
                    try {
                        const response = await fetch('/api/status');
                        const data = await response.json();

                        // Update status
                        this.status.last_sync = data.last_sync;
                        this.status.last_sync_ago = data.last_sync_ago || 'Never';
                        this.status.items_today = data.last_sync_count || 0;
                        this.status.history = data.history || [];
                        this.status.all_healthy = data.last_sync_status !== 'error';

                        // Update job statuses
                        if (data.granola_enabled !== undefined) {
                            this.status.jobs[0].status = data.granola_enabled ? 'success' : 'pending';
                        }
                        if (data.slack_enabled !== undefined) {
                            this.status.jobs[1].status = data.slack_enabled ? 'success' : 'pending';
                        }
                        if (data.morning_push_enabled !== undefined) {
                            this.status.jobs[2].status = data.morning_push_enabled ? 'success' : 'pending';
                        }

                        // Re-init icons
                        this.$nextTick(() => lucide.createIcons());
                    } catch (error) {
                        console.error('Failed to load status:', error);
                    }
                },

                async runJob(jobId) {
                    const job = this.status.jobs.find(j => j.id === jobId);
                    if (job) job.running = true;

                    try {
                        const response = await fetch(`/api/run/${jobId}`, { method: 'POST' });
                        const data = await response.json();
                        this.showToast(data.success ? `✓ ${job.name} completed` : `✗ ${data.error}`);
                        await this.loadStatus();
                    } catch (error) {
                        this.showToast(`✗ Failed: ${error.message}`);
                    } finally {
                        if (job) job.running = false;
                    }
                },

                async runAllJobs() {
                    this.isRunning = true;
                    try {
                        const response = await fetch('/api/run/all', { method: 'POST' });
                        const data = await response.json();
                        this.showToast(data.success ? `✓ Sync complete: ${data.new_todos || 0} items` : `✗ ${data.error}`);
                        await this.loadStatus();
                    } catch (error) {
                        this.showToast(`✗ Failed: ${error.message}`);
                    } finally {
                        this.isRunning = false;
                    }
                },

                showToast(message) {
                    this.toast = message;
                    setTimeout(() => this.toast = null, 3000);
                }
            }
        }
    </script>
</body>
</html>
"""

@flask_app.route('/')
def dashboard():
    return render_template_string(DASHBOARD_HTML)

@flask_app.route('/api/status')
def api_status():
    status = load_status()

    # Calculate time ago
    if status.get('last_sync'):
        try:
            dt = datetime.fromisoformat(status['last_sync'])
            status['last_sync_ago'] = time_ago(dt)
        except:
            status['last_sync_ago'] = 'Unknown'

    # Add upcoming schedule
    next_sync, next_push = get_next_scheduled_times()
    status['next_nightly_sync'] = next_sync
    status['next_morning_push'] = next_push

    return jsonify(status)

@flask_app.route('/api/run/<job_id>', methods=['POST'])
def api_run_job(job_id):
    try:
        if job_id == 'all' or job_id == 'granola' or job_id == 'slack':
            # Run nightly sync
            result = subprocess.run(
                [sys.executable, str(PROJECT_DIR / 'scripts' / 'nightly_sync.py')],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(PROJECT_DIR)
            )
            return jsonify({'success': result.returncode == 0, 'output': result.stdout, 'error': result.stderr})

        elif job_id == 'morning_push':
            result = subprocess.run(
                [sys.executable, str(PROJECT_DIR / 'scripts' / 'morning_push.py')],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(PROJECT_DIR)
            )
            return jsonify({'success': result.returncode == 0, 'output': result.stdout, 'error': result.stderr})

        else:
            return jsonify({'success': False, 'error': 'Unknown job'})

    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'error': 'Job timed out'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def load_status():
    try:
        if STATUS_FILE.exists():
            return json.loads(STATUS_FILE.read_text())
    except:
        pass
    return {}

def time_ago(dt):
    now = datetime.now()
    diff = now - dt
    seconds = diff.total_seconds()

    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        mins = int(seconds / 60)
        return f"{mins}m ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours}h ago"
    else:
        days = int(seconds / 86400)
        return f"{days}d ago"


def get_next_scheduled_times():
    """Calculate next scheduled sync times."""
    from datetime import timedelta

    now = datetime.now()

    # Nightly sync at 11 PM
    nightly = now.replace(hour=23, minute=0, second=0, microsecond=0)
    if now >= nightly:
        nightly += timedelta(days=1)

    # Morning push at 8 AM
    morning = now.replace(hour=8, minute=0, second=0, microsecond=0)
    if now >= morning:
        morning += timedelta(days=1)

    # Format nicely
    def format_time(dt):
        if dt.date() == now.date():
            return f"Today {dt.strftime('%I:%M %p')}"
        elif dt.date() == (now + timedelta(days=1)).date():
            return f"Tomorrow {dt.strftime('%I:%M %p')}"
        else:
            return dt.strftime('%b %d %I:%M %p')

    return format_time(nightly), format_time(morning)


class DigimanMonitor(rumps.App):
    def __init__(self):
        super().__init__("Monitor", title="⚡", quit_button=None)
        self.flask_thread = None
        self.start_flask()
        self.build_menu()

    def start_flask(self):
        """Start Flask server in background thread."""
        def run():
            flask_app.run(port=MONITOR_PORT, debug=False, use_reloader=False)

        self.flask_thread = threading.Thread(target=run, daemon=True)
        self.flask_thread.start()

    def build_menu(self):
        status = load_status()

        # Status indicator
        if status.get('last_sync_status') == 'error':
            self.title = "⚡❌"
            self.menu.add(rumps.MenuItem("❌ Last sync failed", callback=None))
        elif status.get('last_sync'):
            self.title = "⚡"
            try:
                dt = datetime.fromisoformat(status['last_sync'])
                ago = time_ago(dt)
                self.menu.add(rumps.MenuItem(f"✓ Last sync: {ago}", callback=None))
            except:
                self.menu.add(rumps.MenuItem("✓ Synced", callback=None))
        else:
            self.title = "⚡"
            self.menu.add(rumps.MenuItem("No syncs yet", callback=None))

        self.menu.add(None)

        # Upcoming schedule
        next_sync, next_push = get_next_scheduled_times()
        self.menu.add(rumps.MenuItem("📅 Upcoming Schedule", callback=None))
        self.menu.add(rumps.MenuItem(f"   📝 Nightly Sync: {next_sync}", callback=None))
        self.menu.add(rumps.MenuItem(f"   🌅 Morning Push: {next_push}", callback=None))

        self.menu.add(None)
        self.menu.add(rumps.MenuItem("📊 Open Dashboard", callback=self.open_dashboard))
        self.menu.add(rumps.MenuItem("▶️ Run Sync Now", callback=self.run_sync))
        self.menu.add(None)
        self.menu.add(rumps.MenuItem("🧠 Open Digiman", callback=self.open_digiman))

    def open_dashboard(self, _):
        webbrowser.open(f"http://localhost:{MONITOR_PORT}")

    def open_digiman(self, _):
        webbrowser.open("https://manmohanbuildsproducts.pythonanywhere.com")

    def run_sync(self, _):
        rumps.notification("Digiman Monitor", "Starting sync...", "This may take a moment")

        def sync():
            try:
                result = subprocess.run(
                    [sys.executable, str(PROJECT_DIR / 'scripts' / 'nightly_sync.py')],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    cwd=str(PROJECT_DIR)
                )
                if result.returncode == 0:
                    rumps.notification("Digiman Monitor", "✓ Sync complete", "Check dashboard for details")
                else:
                    rumps.notification("Digiman Monitor", "✗ Sync failed", result.stderr[:100] if result.stderr else "Unknown error")
            except Exception as e:
                rumps.notification("Digiman Monitor", "✗ Error", str(e)[:100])

            # Rebuild menu to show updated status
            self.menu.clear()
            self.build_menu()

        threading.Thread(target=sync, daemon=True).start()


if __name__ == "__main__":
    DigimanMonitor().run()
