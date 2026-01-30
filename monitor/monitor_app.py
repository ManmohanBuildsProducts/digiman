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
        .log-viewer { font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace; font-size: 11px; }
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
                <button @click="loadStatus()" class="p-2 text-gray-400 hover:text-white transition-colors" title="Refresh now">
                    <i data-lucide="refresh-cw" class="w-4 h-4"></i>
                </button>
                <span class="text-xs text-gray-500">Auto: 10s</span>
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
                    <span class="text-2xl">🧠</span>
                    <div>
                        <div class="text-sm text-gray-400">SMART_PASTE</div>
                        <div class="font-medium" x-text="status.next_smart_paste || 'Tomorrow 1:30 AM'"></div>
                    </div>
                </div>
                <div class="flex items-center gap-3 p-3 bg-gray-700/50 rounded-lg">
                    <span class="text-2xl">📝</span>
                    <div>
                        <div class="text-sm text-gray-400">Nightly Sync</div>
                        <div class="font-medium" x-text="status.next_nightly_sync || 'Tomorrow 2:00 AM'"></div>
                    </div>
                </div>
                <div class="flex items-center gap-3 p-3 bg-gray-700/50 rounded-lg">
                    <span class="text-2xl">🐕</span>
                    <div>
                        <div class="text-sm text-gray-400">Watchdog</div>
                        <div class="font-medium">Every 15 min <span class="text-green-400 text-xs">(Active)</span></div>
                    </div>
                </div>
                <div class="flex items-center gap-3 p-3 bg-gray-700/50 rounded-lg">
                    <span class="text-2xl">🌅</span>
                    <div>
                        <div class="text-sm text-gray-400">Morning Push</div>
                        <div class="font-medium" x-text="status.next_morning_push || 'Tomorrow 8:00 AM'"></div>
                    </div>
                </div>
            </div>

            <!-- Claude Code Status -->
            <div class="mt-4 p-3 rounded-lg"
                 :class="status.claude_code?.available ? 'bg-green-500/10 border border-green-500/30' : 'bg-yellow-500/10 border border-yellow-500/30'">
                <div class="flex items-center gap-2">
                    <span class="text-lg">🤖</span>
                    <span class="text-sm" :class="status.claude_code?.available ? 'text-green-400' : 'text-yellow-400'"
                          x-text="status.claude_code?.available ? 'Claude Code CLI: Ready' : 'Claude Code CLI: Not detected'"></span>
                </div>
            </div>

            <!-- Backfill Status (if pending) -->
            <div x-show="status.backfill?.pending_days > 0"
                 class="mt-4 p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                <div class="flex items-center gap-2">
                    <span class="text-lg">📅</span>
                    <span class="text-sm text-blue-400">
                        Backfill pending: <span x-text="status.backfill?.pending_days"></span> days
                        (<span x-text="status.backfill?.meetings_pending"></span> meetings)
                    </span>
                </div>
            </div>
        </div>

        <!-- Jobs -->
        <div class="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden mb-8">
            <div class="p-4 border-b border-gray-700 flex items-center justify-between">
                <h2 class="font-bold text-lg">Automation Jobs</h2>
                <a href="#" @click.prevent="showLogs = !showLogs" class="text-xs text-gray-400 hover:text-white flex items-center gap-1">
                    <i data-lucide="terminal" class="w-3 h-3"></i>
                    <span x-text="showLogs ? 'Hide Logs' : 'View Logs'"></span>
                </a>
            </div>
            <div class="divide-y divide-gray-700">
                <template x-for="job in status.jobs" :key="job.name">
                    <div class="p-4 hover:bg-gray-700/30 transition-colors">
                        <div class="flex items-center justify-between">
                            <div class="flex items-center gap-4">
                                <div class="w-10 h-10 rounded-lg flex items-center justify-center"
                                     :class="getJobBgClass(job.status)">
                                    <span x-text="job.icon" class="text-xl"></span>
                                </div>
                                <div>
                                    <div class="flex items-center gap-2">
                                        <span class="font-medium" x-text="job.name"></span>
                                        <span class="text-xs text-gray-500 bg-gray-700 px-1.5 py-0.5 rounded" x-text="job.schedule"></span>
                                    </div>
                                    <div class="text-sm text-gray-400" x-text="job.description"></div>
                                </div>
                            </div>
                            <div class="flex items-center gap-4">
                                <div class="text-right">
                                    <div class="text-sm flex items-center gap-1 justify-end"
                                         :class="getJobStatusClass(job.status)">
                                        <span x-text="getJobStatusText(job)"></span>
                                    </div>
                                    <div class="text-xs text-gray-500" x-text="formatTimeAgo(job.last_run)"></div>
                                </div>
                                <button @click="runJob(job.id)"
                                        :disabled="job.running"
                                        class="px-3 py-1.5 bg-gray-700 rounded-lg text-sm hover:bg-gray-600 transition-colors disabled:opacity-50">
                                    <span x-show="!job.running">Run</span>
                                    <span x-show="job.running" class="pulse">...</span>
                                </button>
                            </div>
                        </div>
                        <!-- Error message if present -->
                        <div x-show="job.status === 'error' && job.last_message"
                             class="mt-2 ml-14 text-xs text-red-400 bg-red-500/10 px-2 py-1 rounded">
                            <span x-text="job.last_message"></span>
                        </div>
                    </div>
                </template>
            </div>
        </div>

        <!-- Logs Viewer (collapsible) -->
        <div x-show="showLogs" x-collapse class="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden mb-8">
            <div class="p-4 border-b border-gray-700 flex items-center justify-between">
                <h2 class="font-bold text-lg flex items-center gap-2">
                    <i data-lucide="terminal" class="w-4 h-4"></i>
                    Recent Logs
                </h2>
                <select x-model="selectedLogFile" @change="loadLogs()" class="bg-gray-700 text-sm rounded px-2 py-1 border-0">
                    <option value="smartpaste">SMART_PASTE</option>
                    <option value="watchdog">Watchdog</option>
                    <option value="nightly">Nightly Sync</option>
                    <option value="morning">Morning Push</option>
                </select>
            </div>
            <div class="p-4 bg-gray-900 max-h-64 overflow-y-auto log-viewer">
                <pre class="text-gray-300 whitespace-pre-wrap" x-text="logContent || 'Click a log file to view...'"></pre>
            </div>
            <div class="p-2 border-t border-gray-700 flex justify-end">
                <a :href="'/api/logs/' + selectedLogFile + '/download'"
                   class="text-xs text-gray-400 hover:text-white flex items-center gap-1">
                    <i data-lucide="download" class="w-3 h-3"></i>
                    Download full log
                </a>
            </div>
        </div>

        <!-- History -->
        <div class="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
            <div class="p-4 border-b border-gray-700">
                <h2 class="font-bold text-lg">Recent Activity</h2>
            </div>
            <div class="divide-y divide-gray-700 max-h-96 overflow-y-auto">
                <template x-for="entry in filteredHistory" :key="entry.timestamp">
                    <div class="p-3 flex items-center gap-3 text-sm">
                        <div class="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0"
                             :class="getHistoryStatusClass(entry.status)">
                            <span x-text="getHistoryIcon(entry.status)" class="text-xs"></span>
                        </div>
                        <div class="flex-1 min-w-0">
                            <span class="text-gray-300" x-text="formatSourceName(entry.source)"></span>
                            <span class="text-gray-500 mx-1">·</span>
                            <span class="text-gray-400" x-text="entry.count + ' items'"></span>
                            <span x-show="entry.error" class="text-red-400 text-xs ml-2" x-text="'— ' + entry.error?.substring(0, 50)"></span>
                        </div>
                        <div class="text-gray-500 text-xs" x-text="formatTimeAgo(entry.timestamp)"></div>
                    </div>
                </template>
                <div x-show="!filteredHistory?.length" class="p-8 text-center text-gray-500">
                    No activity yet. Click "Run All" to start syncing.
                </div>
            </div>
        </div>

        <!-- Footer with log file paths -->
        <div class="mt-6 text-center text-xs text-gray-600">
            Logs: ~/.digiman/logs/ · Dashboard: localhost:5051 ·
            <a href="https://manmohanbuildsproducts.pythonanywhere.com" target="_blank" class="text-gray-500 hover:text-gray-400">Open Digiman →</a>
        </div>

        <!-- Toast -->
        <div x-show="toast" x-transition
             class="fixed bottom-4 right-4 px-4 py-3 rounded-lg shadow-lg bg-gray-700 text-white">
            <span x-text="toast"></span>
        </div>
    </div>

    <script src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js" defer></script>
    <script src="https://unpkg.com/@alpinejs/collapse@3.x.x/dist/cdn.min.js" defer></script>
    <script>
        function monitorApp() {
            return {
                status: {
                    all_healthy: true,
                    last_sync: null,
                    last_sync_ago: 'Never',
                    items_today: 0,
                    jobs: [
                        { id: 'smart_paste', name: 'SMART_PASTE', description: 'Process meetings via Claude Code', icon: '🧠', status: 'pending', last_run: null, running: false, schedule: '1:30 AM' },
                        { id: 'watchdog', name: 'Watchdog', description: 'Ensures sync completes', icon: '🐕', status: 'active', last_run: null, running: false, schedule: 'Every 15 min' },
                        { id: 'nightly', name: 'Nightly Sync', description: 'Extract action items to Digiman', icon: '📝', status: 'pending', last_run: null, running: false, schedule: '2:00 AM' },
                        { id: 'morning_push', name: 'Morning Push', description: 'Send daily todos to Slack', icon: '🌅', status: 'pending', last_run: null, running: false, schedule: '8:00 AM' }
                    ],
                    history: [],
                    backfill: { pending_days: 0, meetings_pending: 0 },
                    claude_code: { available: false }
                },
                isRunning: false,
                toast: null,
                showLogs: false,
                selectedLogFile: 'smartpaste',
                logContent: '',

                get filteredHistory() {
                    // Filter out 'running' status entries
                    return (this.status.history || []).filter(e => e.status !== 'running');
                },

                formatTimeAgo(timestamp) {
                    if (!timestamp) return 'Never';
                    const date = new Date(timestamp);
                    const now = new Date();
                    const seconds = Math.floor((now - date) / 1000);

                    if (seconds < 60) return 'just now';
                    if (seconds < 3600) return Math.floor(seconds / 60) + 'm ago';
                    if (seconds < 86400) return Math.floor(seconds / 3600) + 'h ago';
                    if (seconds < 172800) return 'Yesterday';
                    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                },

                formatSourceName(source) {
                    const names = {
                        'smart_paste': 'SMART_PASTE',
                        'watchdog': 'Watchdog',
                        'nightly_sync': 'Nightly Sync',
                        'morning_push': 'Morning Push'
                    };
                    return names[source] || source || 'Manual';
                },

                getJobBgClass(status) {
                    const classes = {
                        'success': 'bg-green-500/20',
                        'error': 'bg-red-500/20',
                        'running': 'bg-blue-500/20',
                        'skipped': 'bg-gray-600',
                        'triggered': 'bg-yellow-500/20'
                    };
                    return classes[status] || 'bg-gray-700';
                },

                getJobStatusClass(status) {
                    const classes = {
                        'success': 'text-green-400',
                        'error': 'text-red-400',
                        'running': 'text-blue-400',
                        'skipped': 'text-gray-400',
                        'triggered': 'text-yellow-400'
                    };
                    return classes[status] || 'text-gray-500';
                },

                getJobStatusText(job) {
                    if (job.status === 'success') {
                        return job.last_count ? `✓ ${job.last_count} items` : '✓ Success';
                    }
                    if (job.status === 'error') return '✗ Failed';
                    if (job.status === 'running') return '⟳ Running...';
                    if (job.status === 'skipped') return '○ Skipped';
                    if (job.status === 'triggered') return '⚡ Triggered';
                    return '○ Not run';
                },

                getHistoryStatusClass(status) {
                    if (status === 'success') return 'bg-green-500/20 text-green-400';
                    if (status === 'error') return 'bg-red-500/20 text-red-400';
                    if (status === 'skipped') return 'bg-gray-600 text-gray-400';
                    return 'bg-gray-600 text-gray-400';
                },

                getHistoryIcon(status) {
                    if (status === 'success') return '✓';
                    if (status === 'error') return '✗';
                    if (status === 'skipped') return '○';
                    return '·';
                },

                async loadLogs() {
                    try {
                        const response = await fetch(`/api/logs/${this.selectedLogFile}`);
                        const data = await response.json();
                        this.logContent = data.content || 'No logs available';
                    } catch (error) {
                        this.logContent = 'Failed to load logs: ' + error.message;
                    }
                },

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

                        // Update backfill and claude_code status
                        this.status.backfill = data.backfill || { pending_days: 0, meetings_pending: 0 };
                        this.status.claude_code = data.claude_code || { available: false };

                        // Update upcoming schedule times
                        this.status.next_smart_paste = data.next_smart_paste;
                        this.status.next_nightly_sync = data.next_nightly_sync;
                        this.status.next_morning_push = data.next_morning_push;

                        // Update job statuses from server data
                        if (data.jobs) {
                            for (const job of this.status.jobs) {
                                const serverJob = data.jobs[job.id];
                                if (serverJob) {
                                    job.status = serverJob.last_status || 'pending';
                                    job.last_run = serverJob.last_run;
                                    job.last_message = serverJob.last_message;
                                    job.last_count = serverJob.last_count;
                                }
                            }
                        }

                        // Fallback for legacy data format
                        if (!data.jobs) {
                            if (data.granola_enabled !== undefined) {
                                this.status.jobs[2].status = data.granola_enabled ? 'success' : 'pending';
                            }
                            if (data.morning_push_enabled !== undefined) {
                                this.status.jobs[3].status = data.morning_push_enabled ? 'success' : 'pending';
                            }
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
    next_smart_paste, next_sync, next_push = get_next_scheduled_times()
    status['next_smart_paste'] = next_smart_paste
    status['next_nightly_sync'] = next_sync
    status['next_morning_push'] = next_push

    return jsonify(status)

@flask_app.route('/api/run/<job_id>', methods=['POST'])
def api_run_job(job_id):
    try:
        if job_id == 'smart_paste':
            # Run SMART_PASTE sync
            result = subprocess.run(
                [sys.executable, str(PROJECT_DIR / 'scripts' / 'smart_paste' / 'smart_paste_sync.py')],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout for Claude processing
                cwd=str(PROJECT_DIR)
            )
            return jsonify({'success': result.returncode == 0, 'output': result.stdout, 'error': result.stderr})

        elif job_id == 'watchdog':
            # Run watchdog check
            result = subprocess.run(
                ['bash', str(PROJECT_DIR / 'scripts' / 'smart_paste' / 'watchdog.sh')],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(PROJECT_DIR)
            )
            return jsonify({'success': result.returncode == 0, 'output': result.stdout, 'error': result.stderr})

        elif job_id == 'all' or job_id == 'nightly' or job_id == 'granola' or job_id == 'slack':
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

LOG_DIR = Path.home() / ".digiman" / "logs"
LOG_FILES = {
    'smartpaste': 'smartpaste.log',
    'watchdog': 'watchdog.log',
    'nightly': 'nightly.log',
    'morning': 'morning.log'
}

@flask_app.route('/api/logs/<log_name>')
def api_logs(log_name):
    """Get recent log content."""
    if log_name not in LOG_FILES:
        return jsonify({'error': 'Unknown log file'}), 404

    log_file = LOG_DIR / LOG_FILES[log_name]

    if not log_file.exists():
        return jsonify({'content': f'No log file found at {log_file}'})

    try:
        # Read last 100 lines
        content = log_file.read_text()
        lines = content.strip().split('\n')
        recent_lines = lines[-100:] if len(lines) > 100 else lines
        return jsonify({'content': '\n'.join(recent_lines)})
    except Exception as e:
        return jsonify({'content': f'Error reading log: {e}'})

@flask_app.route('/api/logs/<log_name>/download')
def api_logs_download(log_name):
    """Download full log file."""
    from flask import send_file

    if log_name not in LOG_FILES:
        return jsonify({'error': 'Unknown log file'}), 404

    log_file = LOG_DIR / LOG_FILES[log_name]

    if not log_file.exists():
        return jsonify({'error': 'Log file not found'}), 404

    return send_file(log_file, as_attachment=True, download_name=LOG_FILES[log_name])

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

    # SMART_PASTE at 1:30 AM
    smart_paste = now.replace(hour=1, minute=30, second=0, microsecond=0)
    if now >= smart_paste:
        smart_paste += timedelta(days=1)

    # Nightly sync at 2:00 AM
    nightly = now.replace(hour=2, minute=0, second=0, microsecond=0)
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

    return format_time(smart_paste), format_time(nightly), format_time(morning)


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

        # Check watchdog status
        watchdog_active = status.get('jobs', {}).get('watchdog', {}).get('last_status') == 'triggered'

        # Status indicator
        if status.get('last_sync_status') == 'error':
            self.title = "⚡❌"
            self.menu.add(rumps.MenuItem("❌ Last sync failed", callback=None))
        elif watchdog_active:
            self.title = "⚡🐕"
            self.menu.add(rumps.MenuItem("🐕 Watchdog active - catch-up in progress", callback=None))
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
        next_smart_paste, next_sync, next_push = get_next_scheduled_times()
        self.menu.add(rumps.MenuItem("📅 Schedule", callback=None))
        self.menu.add(rumps.MenuItem(f"   🧠 SMART_PASTE: {next_smart_paste}", callback=None))
        self.menu.add(rumps.MenuItem(f"   🐕 Watchdog: Active", callback=None))
        self.menu.add(rumps.MenuItem(f"   📝 Nightly: {next_sync}", callback=None))
        self.menu.add(rumps.MenuItem(f"   🌅 Morning: {next_push}", callback=None))

        self.menu.add(None)
        self.menu.add(rumps.MenuItem("📊 Open Dashboard", callback=self.open_dashboard))
        self.menu.add(rumps.MenuItem("▶️ Run SMART_PASTE Now", callback=self.run_smart_paste))
        self.menu.add(rumps.MenuItem("▶️ Run Full Sync Now", callback=self.run_sync))
        self.menu.add(None)
        self.menu.add(rumps.MenuItem("🧠 Open Digiman", callback=self.open_digiman))

    def open_dashboard(self, _):
        webbrowser.open(f"http://localhost:{MONITOR_PORT}")

    def open_digiman(self, _):
        webbrowser.open("https://manmohanbuildsproducts.pythonanywhere.com")

    def run_smart_paste(self, _):
        rumps.notification("Digiman Monitor", "Starting SMART_PASTE...", "Processing meetings via Claude Code")

        def sync():
            try:
                result = subprocess.run(
                    [sys.executable, str(PROJECT_DIR / 'scripts' / 'smart_paste' / 'smart_paste_sync.py')],
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 minute timeout for Claude processing
                    cwd=str(PROJECT_DIR)
                )
                if result.returncode == 0:
                    rumps.notification("Digiman Monitor", "✓ SMART_PASTE complete", "Check dashboard for details")
                else:
                    rumps.notification("Digiman Monitor", "✗ SMART_PASTE failed", result.stderr[:100] if result.stderr else "Unknown error")
            except Exception as e:
                rumps.notification("Digiman Monitor", "✗ Error", str(e)[:100])

            # Rebuild menu to show updated status
            self.menu.clear()
            self.build_menu()

        threading.Thread(target=sync, daemon=True).start()

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
