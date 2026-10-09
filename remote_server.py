#!/usr/bin/env python3
"""
Notchgent Remote Server - Embedded HTTP and SSE server for mobile remote approvals.
Provides:
  - Mobile Web HUD (single-page responsive PWA)
  - Server-Sent Events (SSE) for real-time instant notification
  - Secure token authentication
  - Direct integration with Notchgent HUD and Antigravity hook bridge
"""

import os
import sys
import json
import time
import secrets
import threading
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Optional, Dict, Any, List, Callable

# Embedded Mobile Web App (HTML5 + CSS3 + Vanilla ES6 JS)
# Styled with Apple Dynamic Island dark aesthetic, orange glowing border, and tactile buttons
MOBILE_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <meta name="theme-color" content="#0d0f14">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <title>Notchgent Remote</title>
  <style>
    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      -webkit-tap-highlight-color: transparent;
      user-select: none;
    }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: #090a0f;
      color: #f3f4f6;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: flex-start;
      padding: 16px 14px 24px;
      overflow-x: hidden;
    }

    /* Top Capsule / Dynamic Island Header */
    .island-header {
      width: 100%;
      max-width: 480px;
      background: rgba(18, 20, 26, 0.95);
      border: 1.5px solid rgba(249, 115, 22, 0.85);
      border-radius: 28px;
      padding: 12px 18px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6), 0 0 16px rgba(249, 115, 22, 0.15);
      backdrop-filter: blur(16px);
      margin-bottom: 20px;
      transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .island-left {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .status-dot {
      width: 11px;
      height: 11px;
      border-radius: 50%;
      background-color: #10b981;
      box-shadow: 0 0 8px #10b981;
      transition: background-color 0.3s, box-shadow 0.3s;
    }
    .status-dot.pending {
      background-color: #f59e0b;
      box-shadow: 0 0 12px #f59e0b;
      animation: pulse-dot 1.2s infinite alternate;
    }
    .status-dot.sending {
      background-color: #3b82f6;
      box-shadow: 0 0 10px #3b82f6;
    }
    @keyframes pulse-dot {
      from { transform: scale(0.9); opacity: 0.7; }
      to { transform: scale(1.25); opacity: 1; }
    }
    .status-title {
      font-size: 14px;
      font-weight: 700;
      letter-spacing: -0.2px;
      color: #ffffff;
    }
    .status-subtitle {
      font-size: 11px;
      color: #9ca3af;
      font-weight: 500;
    }
    .auto-btn {
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.15);
      color: #f3f4f6;
      border-radius: 14px;
      padding: 5px 12px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 4px;
      transition: all 0.2s;
    }
    .auto-btn.active {
      background: #ea580c;
      border-color: #fb923c;
      color: #ffffff;
      box-shadow: 0 0 10px rgba(234, 88, 12, 0.4);
    }
    .mute-btn {
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.15);
      color: #9ca3af;
      border-radius: 14px;
      padding: 5px 9px;
      font-size: 12px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.2s;
    }
    .mute-btn:hover {
      background: rgba(255, 255, 255, 0.16);
      color: #ffffff;
    }
    .mute-btn.muted {
      background: rgba(239, 68, 68, 0.2);
      border-color: rgba(239, 68, 68, 0.5);
      color: #f87171;
    }


    /* Main Container */
    .main-card {
      width: 100%;
      max-width: 480px;
      background: rgba(18, 20, 26, 0.85);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 24px;
      padding: 20px;
      box-shadow: 0 12px 40px rgba(0, 0, 0, 0.7);
      backdrop-filter: blur(20px);
      display: flex;
      flex-direction: column;
      gap: 16px;
      flex: 1;
    }

    /* Idle / Waiting View */
    .idle-view {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      text-align: center;
      padding: 40px 10px;
      gap: 14px;
      color: #9ca3af;
    }
    .idle-icon {
      font-size: 42px;
      margin-bottom: 4px;
      animation: float-icon 3s ease-in-out infinite;
    }
    @keyframes float-icon {
      0%, 100% { transform: translateY(0); }
      50% { transform: translateY(-6px); }
    }
    .idle-title {
      font-size: 18px;
      font-weight: 700;
      color: #ffffff;
    }
    .idle-desc {
      font-size: 13px;
      max-width: 280px;
      line-height: 1.5;
    }

    /* Action View */
    .action-view {
      display: none;
      flex-direction: column;
      gap: 14px;
    }
    .badge-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .tool-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: rgba(139, 92, 246, 0.22);
      border: 1px solid rgba(139, 92, 246, 0.45);
      color: #c4b5fd;
      border-radius: 10px;
      padding: 5px 12px;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.3px;
    }
    .workspace-tag {
      font-size: 12px;
      font-weight: 600;
      color: #f97316;
      background: rgba(249, 115, 22, 0.12);
      padding: 4px 10px;
      border-radius: 8px;
      border: 1px solid rgba(249, 115, 22, 0.25);
    }
    .details-container {
      background: #080a0e;
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 14px;
      padding: 14px;
      max-height: 240px;
      overflow-y: auto;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 12px;
      line-height: 1.5;
      color: #e5e7eb;
      word-break: break-all;
      white-space: pre-wrap;
      user-select: text;
    }

    /* Action Buttons */
    .btn-row {
      display: flex;
      gap: 10px;
      margin-top: 6px;
    }
    .btn {
      flex: 1;
      padding: 16px 12px;
      border-radius: 16px;
      font-size: 16px;
      font-weight: 700;
      border: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      transition: transform 0.1s, filter 0.2s, opacity 0.2s;
    }
    .btn:active {
      transform: scale(0.97);
    }
    .btn-approve {
      background: linear-gradient(135deg, #10b981 0%, #059669 100%);
      color: #ffffff;
      flex: 2;
      box-shadow: 0 4px 18px rgba(16, 185, 129, 0.35);
    }
    .btn-approve:hover {
      filter: brightness(1.1);
    }
    .btn-reject {
      background: rgba(239, 68, 68, 0.16);
      border: 1.5px solid rgba(239, 68, 68, 0.4);
      color: #f87171;
      flex: 1;
    }
    .btn-reject:hover {
      background: rgba(239, 68, 68, 0.28);
    }

    /* Feedback Banner */
    .feedback-banner {
      display: none;
      align-items: center;
      justify-content: center;
      gap: 8px;
      padding: 12px;
      border-radius: 12px;
      font-size: 14px;
      font-weight: 700;
      text-align: center;
      animation: fadeIn 0.2s ease-out;
    }
    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(-4px); }
      to { opacity: 1; transform: translateY(0); }
    }
    .feedback-banner.success {
      background: rgba(16, 185, 129, 0.2);
      border: 1px solid rgba(16, 185, 129, 0.5);
      color: #34d399;
    }
    .feedback-banner.danger {
      background: rgba(239, 68, 68, 0.2);
      border: 1px solid rgba(239, 68, 68, 0.5);
      color: #fca5a5;
    }

    /* Footer Info */
    .footer-bar {
      width: 100%;
      max-width: 480px;
      margin-top: 14px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 11px;
      color: #6b7280;
      padding: 0 6px;
    }
    .connection-tag {
      display: flex;
      align-items: center;
      gap: 5px;
    }
    .conn-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: #10b981;
    }
  </style>
</head>
<body>

  <!-- Dynamic Island Header -->
  <div class="island-header" id="islandHeader">
    <div class="island-left">
      <div class="status-dot" id="statusDot"></div>
      <div>
        <div class="status-title" id="statusTitle">Notchgent • Idle</div>
        <div class="status-subtitle" id="statusSubtitle">PC Connected at Home</div>
      </div>
    </div>
    <div style="display:flex;align-items:center;gap:6px;">
      <button class="mute-btn" id="muteBtn" onclick="toggleMute()" title="Mute sound chime">
        <span id="muteIcon" style="display:flex;align-items:center;"><svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/></svg></span>
      </button>
      <button class="auto-btn" id="autoBtn" onclick="toggleAutoMode()">
        <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;"><path d="M4 11v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8H4z"/><path d="m4 11 3-6h4l-3 6"/><path d="m11 5 3 6"/><path d="m14 5 3 6"/><path d="m17 5 3 6"/><path d="M2 11h20"/></svg>
        <span id="autoBtnText">Auto</span>
      </button>
    </div>
  </div>

  <!-- Main Card -->
  <div class="main-card">
    <div id="feedbackBanner" class="feedback-banner"></div>

    <!-- Idle View -->
    <div class="idle-view" id="idleView">
      <div class="idle-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="46" height="46" viewBox="0 0 24 24" fill="none" stroke="#f97316" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block;"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
      </div>
      <div class="idle-title">Agent is Working</div>
      <div class="idle-desc">Whenever Antigravity requests approval, this screen will chime and spring open instantly.</div>
    </div>

    <!-- Pending Action View -->
    <div class="action-view" id="actionView">
      <div class="badge-row">
        <div class="tool-badge" id="toolBadge">
          <span id="toolBadgeIcon" style="display:inline-flex;align-items:center;"><svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg></span>
          <span id="toolBadgeText">Tool Execution</span>
        </div>
        <div class="workspace-tag" id="workspaceTag">Workspace</div>
      </div>

      <div class="details-container" id="detailsBox">
        Waiting for action details...
      </div>

      <div class="btn-row">
        <button class="btn btn-approve" id="approveBtn" onclick="dispatchAction('1')">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;"><polyline points="20 6 9 17 4 12"/></svg>
          <span>Approve</span>
        </button>
        <button class="btn btn-reject" id="rejectBtn" onclick="dispatchAction('2')">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#f87171" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          <span>Reject</span>
        </button>
      </div>
    </div>
  </div>

  <!-- Footer Info -->
  <div class="footer-bar">
    <div class="connection-tag">
      <div class="conn-dot" id="connDot"></div>
      <span id="connText">Secure Tunnel Active</span>
    </div>
    <div id="batteryTime" style="display:flex;align-items:center;gap:4px;">
      <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#6b7280" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>
      <span>Encrypted Session</span>
    </div>
  </div>


  <script>
    // Extract token from URL hash or query params
    function getToken() {
      const hash = window.location.hash.substring(1);
      const hashParams = new URLSearchParams(hash);
      if (hashParams.get('token')) return hashParams.get('token');

      const urlParams = new URLSearchParams(window.location.search);
      if (urlParams.get('token')) return urlParams.get('token');

      return localStorage.getItem('notchgent_token') || '';
    }

    const token = getToken();
    if (token) {
      localStorage.setItem('notchgent_token', token);
    }

    let isAutoActive = false;
    let isMuted = false;
    let currentStep = -1;
    let lastDispatchedStep = -1;
    let isSubmitting = false;

    const SVGS = {
      terminal: '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>',
      file_edit: '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>',
      file_plus: '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/><line x1="9" y1="15" x2="15" y2="15"/></svg>',
      help_circle: '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
      zap: '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>',
      volume_2: '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>',
      volume_x: '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/></svg>'
    };

    function updateMuteUI(muted) {
      isMuted = !!muted;
      const muteBtn = document.getElementById('muteBtn');
      const muteIcon = document.getElementById('muteIcon');
      if (!muteBtn || !muteIcon) return;
      if (isMuted) {
        muteBtn.classList.add('muted');
        muteBtn.title = 'Unmute Sound / Chime';
        muteIcon.innerHTML = SVGS.volume_x;
      } else {
        muteBtn.classList.remove('muted');
        muteBtn.title = 'Mute Sound / Chime';
        muteIcon.innerHTML = SVGS.volume_2;
      }
    }

    async function toggleMute() {
      triggerHaptic([30]);
      try {
        const res = await fetch('/api/toggle_mute', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + token
          }
        });
        const data = await res.json();
        updateMuteUI(data.muted);
        showFeedback(data.muted ? 'Sound Muted' : 'Sound Enabled', 'info', 1500);
      } catch (e) {
        updateMuteUI(!isMuted);
      }
    }

    // Web Audio alert chime
    function playChime() {
      if (isMuted) return;
      try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(880, audioCtx.currentTime); // A5
        osc.frequency.exponentialRampToValueAtTime(1320, audioCtx.currentTime + 0.08); // E6
        gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.16);
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start();
        osc.stop(audioCtx.currentTime + 0.18);
      } catch (e) {}
    }

    // Haptic vibration feedback
    function triggerHaptic(pattern = [50]) {
      if (navigator.vibrate) {
        try { navigator.vibrate(pattern); } catch (e) {}
      }
    }

    function showFeedback(text, type = 'success', duration = 2500) {
      const banner = document.getElementById('feedbackBanner');
      banner.textContent = text;
      banner.className = 'feedback-banner ' + type;
      banner.style.display = 'flex';
      setTimeout(() => {
        banner.style.display = 'none';
      }, duration);
    }

    function updateUI(data) {
      const status = data.status;
      const action = data.action;
      const workspace = data.workspace || '';
      isAutoActive = !!data.auto_active;
      if (data.is_muted !== undefined) {
        updateMuteUI(data.is_muted);
      }

      // Update Auto button state
      const autoBtn = document.getElementById('autoBtn');
      const autoBtnText = document.getElementById('autoBtnText');
      if (isAutoActive) {
        autoBtn.classList.add('active');
        if (autoBtnText) autoBtnText.textContent = 'Active';
      } else {
        autoBtn.classList.remove('active');
        if (autoBtnText) autoBtnText.textContent = 'Auto';
      }

      const statusDot = document.getElementById('statusDot');
      const statusTitle = document.getElementById('statusTitle');
      const statusSubtitle = document.getElementById('statusSubtitle');
      const idleView = document.getElementById('idleView');
      const actionView = document.getElementById('actionView');

      if (status === 'pending' && action) {
        // If we already approved/rejected this exact step, don't re-show the buttons
        if (action.step_index === lastDispatchedStep) {
          return;
        }

        // Only chime if brand new step
        if (action.step_index !== currentStep) {
          currentStep = action.step_index;
          playChime();
          triggerHaptic([70, 40, 70]);
        }

        statusDot.className = 'status-dot pending';
        statusTitle.textContent = workspace ? 'Approval Needed • ' + workspace : 'Approval Needed';
        statusSubtitle.textContent = 'Step ' + action.step_index;

        idleView.style.display = 'none';
        actionView.style.display = 'flex';

        const toolConfigs = {
          'run_command': { svg: SVGS.terminal, name: 'Shell Command' },
          'replace_file_content': { svg: SVGS.file_edit, name: 'Edit File' },
          'write_to_file': { svg: SVGS.file_plus, name: 'Create File' },
          'ask_question': { svg: SVGS.help_circle, name: 'Question' }
        };

        const conf = toolConfigs[action.tool_name] || { svg: SVGS.zap, name: action.tool_name };
        const badgeIconEl = document.getElementById('toolBadgeIcon');
        const badgeTextEl = document.getElementById('toolBadgeText');
        if (badgeIconEl) badgeIconEl.innerHTML = conf.svg;
        if (badgeTextEl) badgeTextEl.textContent = conf.name;
        document.getElementById('workspaceTag').textContent = workspace || 'antigravity';

        // Format details
        let details = '';
        const args = action.args || {};
        if (action.tool_name === 'run_command') {
          details = '> ' + (args.CommandLine || '');
        } else if (action.tool_name === 'replace_file_content' || action.tool_name === 'write_to_file') {
          const path = args.TargetFile || '';
          const name = path.split(/[\\\\/]/).pop();
          const instr = args.Instruction || args.Description || args.toolAction || '';
          details = 'File: ' + name + '\\n' + instr;
        } else {
          details = JSON.stringify(args, null, 2);
        }
        document.getElementById('detailsBox').textContent = details;

      } else {
        currentStep = -1;
        lastDispatchedStep = -1;
        statusDot.className = 'status-dot';
        statusTitle.textContent = isAutoActive ? 'Auto Mode Active' : 'Notchgent • Idle';
        statusSubtitle.textContent = workspace ? 'Project: ' + workspace : 'PC Connected at Home';

        idleView.style.display = 'flex';
        actionView.style.display = 'none';
      }
    }

    async function dispatchAction(key) {
      if (isSubmitting) return;
      isSubmitting = true;
      triggerHaptic(key === '1' ? [40] : [70]);

      const statusDot = document.getElementById('statusDot');
      statusDot.className = 'status-dot sending';
      const label = key === '1' ? 'Approving...' : 'Rejecting...';
      document.getElementById('statusTitle').textContent = label;

      try {
        const res = await fetch('/api/action', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + token
          },
          body: JSON.stringify({ key: key, step_index: currentStep })
        });
        const resData = await res.json();
        if (resData.ok) {
          lastDispatchedStep = currentStep;
          showFeedback(key === '1' ? 'Dispatched Approval (1)' : 'Dispatched Reject (2)', key === '1' ? 'success' : 'danger');

          // Immediately clear the action card and restore idle state on phone
          statusDot.className = 'status-dot';
          statusTitle.textContent = key === '1' ? 'Sent 1' : 'Sent 2';
          statusSubtitle.textContent = 'Dispatched to PC';
          document.getElementById('actionView').style.display = 'none';
          document.getElementById('idleView').style.display = 'flex';
        } else {

          showFeedback('Error: ' + (resData.error || 'Failed'), 'danger');
        }
      } catch (e) {
        showFeedback('Connection Error: ' + e.message, 'danger');
      } finally {
        setTimeout(() => { isSubmitting = false; }, 600);
      }
    }

    async function toggleAutoMode() {
      triggerHaptic([30]);
      try {
        const res = await fetch('/api/toggle_auto', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + token
          }
        });
        const data = await res.json();
        isAutoActive = !!data.auto_active;
        document.getElementById('autoBtn').classList.toggle('active', isAutoActive);
      } catch (e) {}
    }

    // Fast Polling Watchdog (750ms)
    // Ensures instant responsiveness with zero delay even on cellular networks or buffered proxies
    async function pollStatus() {
      try {
        const res = await fetch('/api/status?token=' + encodeURIComponent(token), { cache: 'no-store' });
        if (res.ok) {
          const data = await res.json();
          updateUI(data);
        }
      } catch (e) {}
    }
    setInterval(pollStatus, 750);

    // SSE Realtime Connection
    let eventSource = null;
    function connectSSE() {
      if (eventSource) eventSource.close();

      const sseUrl = '/api/events?token=' + encodeURIComponent(token);
      eventSource = new EventSource(sseUrl);

      eventSource.onopen = () => {
        document.getElementById('connDot').style.background = '#10b981';
        document.getElementById('connText').textContent = 'Live Stream Connected';
      };

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          updateUI(data);
        } catch (e) {}
      };

      eventSource.onerror = () => {
        document.getElementById('connDot').style.background = '#ef4444';
        document.getElementById('connText').textContent = 'Reconnecting...';
        eventSource.close();
        setTimeout(connectSSE, 2500);
      };
    }

    // Auto-fetch initial state and connect
    async function loadInitial() {
      await pollStatus();
      connectSSE();
    }

    window.addEventListener('load', loadInitial);
    // Auto-reconnect on visibility change (e.g. phone unlocks)
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden) {
        loadInitial();
      }
    });
  </script>
</body>
</html>
"""


class RemoteServer:
    """Embedded HTTP and SSE server managing mobile approvals and token security."""

    def __init__(
        self,
        port: int = 5151,
        on_action_callback: Optional[Callable[[str], bool]] = None,
        on_toggle_auto_callback: Optional[Callable[[], bool]] = None,
        on_toggle_mute_callback: Optional[Callable[[], bool]] = None,
        is_muted: bool = False
    ):
        self.port = port
        self.token = secrets.token_hex(16)
        self.on_action_callback = on_action_callback
        self.on_toggle_auto_callback = on_toggle_auto_callback
        self.on_toggle_mute_callback = on_toggle_mute_callback

        self._state: Dict[str, Any] = {
            "status": "idle",
            "action": None,
            "workspace": "",
            "auto_active": False,
            "is_muted": is_muted
        }
        self._lock = threading.Lock()
        self._sse_clients: List[Any] = []
        self._httpd: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self.connected_devices_count = 0

    def rotate_token(self) -> str:
        """Invalidate previous token and generate a new secure session token."""
        with self._lock:
            self.token = secrets.token_hex(16)
            # Notify all SSE clients of token revocation by closing connections
            for client in list(self._sse_clients):
                try:
                    client.close()
                except Exception:
                    pass
            self._sse_clients.clear()
            self.connected_devices_count = 0
            return self.token

    def update_state(
        self,
        status: str,
        action: Optional[Dict[str, Any]] = None,
        workspace: str = "",
        auto_active: Optional[bool] = None,
        is_muted: Optional[bool] = None
    ):
        """Update current agent approval state and broadcast to all connected phones."""
        with self._lock:
            self._state["status"] = status
            self._state["action"] = action
            if workspace:
                self._state["workspace"] = workspace
            if auto_active is not None:
                self._state["auto_active"] = auto_active
            if is_muted is not None:
                self._state["is_muted"] = is_muted
            payload = json.dumps(self._state)

        # Broadcast SSE message to all connected clients
        msg = f"data: {payload}\n\n".encode("utf-8")
        dead_clients = []
        with self._lock:
            for client in list(self._sse_clients):
                try:
                    client.wfile.write(msg)
                    client.wfile.flush()
                except Exception:
                    dead_clients.append(client)
            for dc in dead_clients:
                if dc in self._sse_clients:
                    self._sse_clients.remove(dc)
            self.connected_devices_count = len(self._sse_clients)

    def start(self):
        """Start the HTTP server on a background daemon thread."""
        server_self = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                # Suppress noisy default HTTP request console logs
                pass

            def check_auth(self) -> bool:
                # 1. Bearer token in Authorization header
                auth_header = self.headers.get("Authorization", "")
                if auth_header.startswith("Bearer "):
                    if auth_header[7:].strip() == server_self.token:
                        return True

                # 2. Token in query parameter
                parsed = urllib.parse.urlparse(self.path)
                params = urllib.parse.parse_qs(parsed.query)
                token_val = params.get("token", [""])[0]
                if token_val == server_self.token:
                    return True

                return False

            def send_json(self, data: dict, status_code: int = 200):
                body = json.dumps(data).encode("utf-8")
                self.send_response(status_code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)

            def do_OPTIONS(self):
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
                self.end_headers()

            def do_GET(self):
                parsed = urllib.parse.urlparse(self.path)
                path = parsed.path

                # Mobile Web App Dashboard
                if path in ("/", "/index.html", "/app"):
                    body = MOBILE_HTML_TEMPLATE.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                    self.end_headers()
                    self.wfile.write(body)
                    return

                # Health & Heartbeat API (used by TunnelManager watchdog)
                if path in ("/api/health", "/api/ping"):
                    self.send_json({"ok": True, "time": time.time(), "devices": server_self.connected_devices_count})
                    return

                # Status API
                if path == "/api/status":
                    if not self.check_auth():
                        self.send_json({"error": "Unauthorized"}, 401)
                        return
                    with server_self._lock:
                        data = dict(server_self._state)
                    self.send_json(data)
                    return


                # SSE Stream
                if path == "/api/events":
                    if not self.check_auth():
                        self.send_json({"error": "Unauthorized"}, 401)
                        return

                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache, no-transform")
                    self.send_header("Connection", "keep-alive")
                    self.send_header("X-Accel-Buffering", "no")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()

                    # Send immediate current state
                    with server_self._lock:
                        initial_payload = json.dumps(server_self._state)
                        server_self._sse_clients.append(self)
                        server_self.connected_devices_count = len(server_self._sse_clients)

                    init_msg = f"data: {initial_payload}\n\n".encode("utf-8")
                    try:
                        self.wfile.write(init_msg)
                        self.wfile.flush()
                    except Exception:
                        with server_self._lock:
                            if self in server_self._sse_clients:
                                server_self._sse_clients.remove(self)
                        return

                    # Keep connection alive with heartbeat pings
                    try:
                        while getattr(server_self, "_running", True):
                            time.sleep(15)
                            self.wfile.write(b": heartbeat\n\n")
                            self.wfile.flush()
                    except Exception:
                        pass
                    finally:
                        with server_self._lock:
                            if self in server_self._sse_clients:
                                server_self._sse_clients.remove(self)
                            server_self.connected_devices_count = len(server_self._sse_clients)
                    return

                self.send_json({"error": "Not Found"}, 404)

            def do_POST(self):
                parsed = urllib.parse.urlparse(self.path)
                path = parsed.path

                # Antigravity hook bridge endpoint (localhost bridge.py support)
                if path == "/request":
                    content_len = int(self.headers.get("Content-Length", 0))
                    body = self.rfile.read(content_len).decode("utf-8", errors="ignore")
                    # For hook bridge requests from localhost:
                    try:
                        payload = json.loads(body)
                    except Exception:
                        payload = {}
                    # Reply allow/ask
                    self.send_json({"decision": "ask"})
                    return

                # Remote mobile actions require auth token
                if not self.check_auth():
                    self.send_json({"error": "Unauthorized"}, 401)
                    return

                content_len = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_len).decode("utf-8", errors="ignore")
                try:
                    payload = json.loads(body)
                except Exception:
                    payload = {}

                if path == "/api/action":
                    key = payload.get("key", "1")
                    success = True
                    if server_self.on_action_callback:
                        success = server_self.on_action_callback(key)
                    self.send_json({"ok": success, "key": key})
                    return

                if path == "/api/toggle_auto":
                    auto_val = False
                    if server_self.on_toggle_auto_callback:
                        auto_val = server_self.on_toggle_auto_callback()
                    self.send_json({"ok": True, "auto_active": auto_val})
                    return

                if path == "/api/toggle_mute":
                    muted_val = False
                    if server_self.on_toggle_mute_callback:
                        muted_val = server_self.on_toggle_mute_callback()
                    with server_self._lock:
                        server_self._state["is_muted"] = muted_val
                    self.send_json({"ok": True, "muted": muted_val})
                    return

                self.send_json({"error": "Not Found"}, 404)

        self._running = True
        self._httpd = ThreadingHTTPServer(("0.0.0.0", self.port), Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
