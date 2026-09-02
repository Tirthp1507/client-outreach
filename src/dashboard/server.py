"""Local web server and approval dashboard for B2B Client Outreach & Content Automation."""

from __future__ import annotations

import json
import logging
import mimetypes
import os
import urllib.parse
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional

from analytics import AnalyticsCollector, AnalyticsReporter, PerformanceInsightsEngine
from b2b.discovery import DiscoveryRegistry, DiscoveryService
from b2b.email_provider import (
    ApprovalGateError,
    BaseEmailProvider,
    ConsoleEmailProvider,
    OutreachSendingService,
    SMTPEmailProvider,
)
from b2b.fixtures import (
    build_sample_business_dataset,
    generate_sample_research,
    sample_business_records,
)
from b2b.models import (
    ApprovalStatus,
    BusinessRecord,
    BusinessStatus,
    FollowUpRecord,
    FollowUpStatus,
    OpportunityRecord,
    OutreachRecord,
    OutreachResponse,
    ReplyStatus,
    ResponseClassification,
    SendStatus,
)
from b2b.pipeline import BusinessIntelligenceService
from b2b.research import ResearchRegistry
from b2b.research_engine import HTTPWebResearchProvider
from b2b.scheduler_intent import BusinessCycleContext
from config import PROJECT_ROOT, get_config
from db.database import Database
from db.models import JobStatus
from pipeline.recovery import JobRecoveryEngine
from pipeline.safeguards import PublishQuotaGuard, StoragePruningEngine, SystemHealthMonitor
from publishers import InstagramPublisher, PublisherService, YouTubePublisher

logger = logging.getLogger(__name__)


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Content Studio — B2B Client Outreach & Automation Hub</title>
  <style>
    :root {
      --bg: #0b0f19;
      --card-bg: #131b2e;
      --card-hover: #1b253e;
      --border: #1e293b;
      --accent: #38bdf8;
      --accent-glow: rgba(56, 189, 248, 0.2);
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --green: #10b981;
      --yellow: #f59e0b;
      --red: #ef4444;
      --purple: #a855f7;
      --indigo: #6366f1;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }
    /* Top Navbar */
    #topbar {
      height: 58px;
      background: var(--card-bg);
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 20px;
      flex-shrink: 0;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 16px;
      font-weight: 700;
      color: var(--text);
    }
    .brand-badge {
      background: rgba(56, 189, 248, 0.15);
      color: var(--accent);
      border: 1px solid var(--accent);
      padding: 2px 8px;
      border-radius: 6px;
      font-size: 11px;
      text-transform: uppercase;
      font-weight: 600;
    }
    .mode-pill {
      background: rgba(245, 158, 11, 0.15);
      color: var(--yellow);
      border: 1px solid var(--yellow);
      padding: 4px 12px;
      border-radius: 20px;
      font-size: 11px;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 6px;
      cursor: pointer;
    }
    .mode-pill.real {
      background: rgba(16, 185, 129, 0.15);
      color: var(--green);
      border-color: var(--green);
    }
    .nav-tabs {
      display: flex;
      gap: 4px;
    }
    .nav-tab {
      padding: 8px 16px;
      background: transparent;
      border: 1px solid transparent;
      border-radius: 8px;
      color: var(--text-muted);
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s;
    }
    .nav-tab:hover { color: var(--text); background: rgba(255,255,255,0.05); }
    .nav-tab.active {
      color: var(--accent);
      background: rgba(56, 189, 248, 0.1);
      border-color: rgba(56, 189, 248, 0.3);
    }
    .btn {
      padding: 6px 14px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      border: 1px solid transparent;
      transition: all 0.15s;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      text-decoration: none;
    }
    .btn-primary { background: var(--accent); color: #000; }
    .btn-primary:hover { background: #7dd3fc; }
    .btn-success { background: var(--green); color: #000; }
    .btn-success:hover { background: #34d399; }
    .btn-danger { background: rgba(239, 68, 68, 0.2); color: var(--red); border-color: var(--red); }
    .btn-danger:hover { background: var(--red); color: #fff; }
    .btn-outline { background: transparent; border-color: var(--border); color: var(--text); }
    .btn-outline:hover { background: rgba(255,255,255,0.05); border-color: var(--text-muted); }

    /* App Body */
    #app-body {
      flex: 1;
      display: flex;
      overflow: hidden;
    }

    /* Left Sidebar: Leads List */
    #sidebar {
      width: 350px;
      background: var(--card-bg);
      border-right: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      flex-shrink: 0;
    }
    .sidebar-header {
      padding: 14px 16px;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .filter-group {
      padding: 8px 14px;
      display: flex;
      gap: 5px;
      border-bottom: 1px solid var(--border);
      background: rgba(0,0,0,0.15);
      flex-wrap: wrap;
    }
    .filter-chip {
      padding: 2px 7px;
      border-radius: 4px;
      font-size: 11px;
      border: 1px solid var(--border);
      background: transparent;
      color: var(--text-muted);
      cursor: pointer;
    }
    .filter-chip.active {
      background: var(--accent);
      color: #000;
      font-weight: 600;
      border-color: var(--accent);
    }
    #leads-list {
      flex: 1;
      overflow-y: auto;
      list-style: none;
    }
    .lead-item {
      padding: 12px 16px;
      border-bottom: 1px solid var(--border);
      cursor: pointer;
      transition: background 0.15s;
    }
    .lead-item:hover { background: var(--card-hover); }
    .lead-item.selected {
      background: rgba(56, 189, 248, 0.1);
      border-left: 3px solid var(--accent);
    }
    .lead-title {
      font-size: 13.5px;
      font-weight: 600;
      color: var(--text);
      margin-bottom: 3px;
    }
    .lead-sub {
      font-size: 11.5px;
      color: var(--text-muted);
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: 4px;
    }

    /* Badges */
    .badge {
      padding: 2px 7px;
      border-radius: 4px;
      font-size: 10px;
      font-weight: 600;
      text-transform: uppercase;
      display: inline-block;
    }
    .badge-discovered { background: rgba(148, 163, 184, 0.15); color: #cbd5e1; border: 1px solid #64748b; }
    .badge-researched { background: rgba(56, 189, 248, 0.15); color: var(--accent); border: 1px solid var(--accent); }
    .badge-scored { background: rgba(168, 85, 247, 0.15); color: var(--purple); border: 1px solid var(--purple); }
    .badge-demo_ready { background: rgba(99, 102, 241, 0.15); color: #818cf8; border: 1px solid #6366f1; }
    .badge-outreach_ready, .badge-pending_review { background: rgba(245, 158, 11, 0.15); color: var(--yellow); border: 1px solid var(--yellow); }
    .badge-approved { background: rgba(16, 185, 129, 0.15); color: var(--green); border: 1px solid var(--green); }
    .badge-sent { background: rgba(16, 185, 129, 0.25); color: #34d399; border: 1px solid var(--green); }
    .badge-replied { background: rgba(236, 72, 153, 0.2); color: #f472b6; border: 1px solid #ec4899; }
    .badge-rejected { background: rgba(239, 68, 68, 0.15); color: var(--red); border: 1px solid var(--red); }
    .badge-suppressed { background: rgba(239, 68, 68, 0.25); color: #fca5a5; border: 1px solid var(--red); }

    /* Main Content Area */
    #main-content {
      flex: 1;
      overflow-y: auto;
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    /* Views */
    .tab-view { display: none; }
    .tab-view.active { display: flex; flex-direction: column; gap: 16px; }

    /* Pipeline Progression Stepper */
    .stepper-bar {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 12px 18px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 6px;
      overflow-x: auto;
    }
    .step-node {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 11px;
      font-weight: 600;
      color: var(--text-muted);
      white-space: nowrap;
    }
    .step-node.active { color: var(--accent); }
    .step-node.completed { color: var(--green); }
    .step-num {
      width: 18px;
      height: 18px;
      border-radius: 50%;
      background: rgba(255,255,255,0.1);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 10px;
    }
    .step-node.active .step-num { background: var(--accent); color: #000; }
    .step-node.completed .step-num { background: var(--green); color: #000; }
    .step-arrow { color: #334155; font-size: 12px; }

    /* 3-Column Studio Grid */
    .studio-grid {
      display: grid;
      grid-template-columns: 340px 440px 1fr;
      gap: 18px;
      align-items: start;
    }
    @media (max-width: 1440px) {
      .studio-grid { grid-template-columns: 1fr 1fr; }
    }

    /* Cards */
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 18px;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }
    .card-title {
      font-size: 13px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--text-muted);
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid var(--border);
      padding-bottom: 8px;
    }

    /* Evidence Box */
    .evidence-item {
      padding: 8px 10px;
      border-radius: 6px;
      background: rgba(0,0,0,0.25);
      border: 1px solid var(--border);
      margin-bottom: 6px;
      font-size: 11.5px;
      line-height: 1.4;
    }
    .evidence-item.fact { border-left: 3px solid var(--green); }
    .evidence-item.inference { border-left: 3px solid var(--purple); }
    .evidence-item.unknown { border-left: 3px solid var(--yellow); }

    /* Score Box */
    .score-banner {
      background: rgba(56, 189, 248, 0.08);
      border: 1px solid var(--accent);
      border-radius: 8px;
      padding: 12px 14px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .score-number {
      font-size: 26px;
      font-weight: 800;
      color: var(--accent);
    }

    /* Form Fields */
    .form-group {
      display: flex;
      flex-direction: column;
      gap: 5px;
    }
    .form-label {
      font-size: 11.5px;
      font-weight: 600;
      color: var(--text-muted);
    }
    .form-input, .form-textarea, .form-select {
      background: #0d1424;
      border: 1px solid var(--border);
      border-radius: 6px;
      color: var(--text);
      padding: 8px 10px;
      font-size: 12.5px;
      font-family: inherit;
    }
    .form-textarea { resize: vertical; min-height: 130px; font-family: monospace; font-size: 11.5px; line-height: 1.4; }
    .form-input:focus, .form-textarea:focus, .form-select:focus {
      outline: none;
      border-color: var(--accent);
      box-shadow: 0 0 0 2px var(--accent-glow);
    }

    /* Demo Iframe Box */
    .demo-frame-container {
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
      height: 380px;
      background: #fff;
    }
    .demo-frame {
      width: 100%;
      height: 100%;
      border: none;
    }

    /* Stats Grid */
    .stats-row {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 14px;
    }
    .stat-card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 14px;
    }
    .stat-val { font-size: 22px; font-weight: 800; color: var(--accent); margin-top: 4px; }
    .stat-lbl { font-size: 11px; color: var(--text-muted); text-transform: uppercase; font-weight: 600; }

    /* Tables */
    .data-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12.5px;
    }
    .data-table th {
      text-align: left;
      padding: 9px 12px;
      background: rgba(0,0,0,0.25);
      border-bottom: 1px solid var(--border);
      color: var(--text-muted);
      font-weight: 600;
    }
    .data-table td {
      padding: 10px 12px;
      border-bottom: 1px solid var(--border);
    }
    .data-table tr:hover td { background: rgba(255,255,255,0.02); }

    /* Toast */
    #toast {
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: #1e293b;
      color: #fff;
      padding: 12px 20px;
      border-radius: 8px;
      font-size: 13px;
      font-weight: 600;
      border: 1px solid var(--accent);
      box-shadow: 0 10px 25px rgba(0,0,0,0.5);
      display: none;
      z-index: 1000;
    }
  </style>
</head>
<body>

  <!-- Top Navbar -->
  <div id="topbar">
    <div class="brand">
      <span>B2B Client Outreach Studio</span>
      <span class="brand-badge">Automated AI Pipeline</span>
      <div id="modePill" class="mode-pill" onclick="toggleSendMode()">
        <span style="width:8px;height:8px;border-radius:50%;background:var(--yellow);display:inline-block;"></span>
        <span id="modeText">MOCK / DRY-RUN (Safe Audit Mode)</span>
      </div>
    </div>

    <div class="nav-tabs">
      <button class="nav-tab active" onclick="switchTab('studio')">Lead Studio</button>
      <button class="nav-tab" onclick="switchTab('responses')">Response & Follow-up Center</button>
      <button class="nav-tab" onclick="switchTab('analytics')">Sales Intelligence & Funnel</button>
    </div>

    <div style="display: flex; gap: 10px; align-items: center;">
      <button class="btn btn-primary" onclick="openDiscoveryModal()">
        <span>📍 Discover Leads & Run Pipeline</span>
      </button>
    </div>
  </div>

  <!-- Live Lead Discovery Modal -->
  <div id="discoveryModal" style="display:none; position:fixed; inset:0; background:rgba(15,23,42,0.85); backdrop-filter:blur(8px); z-index:9999; align-items:center; justify-content:center; padding:16px;">
    <div style="background:#0f172a; border:1px solid var(--border); border-radius:16px; max-width:460px; width:100%; padding:28px; box-shadow:0 25px 50px rgba(0,0,0,0.6);">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; border-bottom:1px solid var(--border); padding-bottom:12px;">
        <h3 style="font-size:16px; font-weight:800; color:var(--text);">📍 Run Custom Lead Discovery</h3>
        <button onclick="closeDiscoveryModal()" style="background:transparent; border:none; color:var(--text-muted); font-size:18px; cursor:pointer;">✕</button>
      </div>

      <div class="form-group" style="margin-bottom:16px;">
        <label class="form-label">1. Target City / Location</label>
        <input id="disc-city" class="form-input" type="text" value="Ahmedabad" placeholder="e.g. Ahmedabad, Mumbai, New York...">
      </div>

      <div class="form-group" style="margin-bottom:16px;">
        <label class="form-label">2. Target Business Vertical</label>
        <select id="disc-category" class="form-select">
          <option value="all">🌐 All Verticals (Salons, Restaurants, Clinics, Gyms, Coaching, Retail)</option>
          <option value="salon">✂️ Salons & Spas</option>
          <option value="restaurant">🍽️ Restaurants & Cafes</option>
          <option value="clinic">⚕️ Clinics & Hospitals</option>
          <option value="gym">🏋️‍♂️ Gyms & Fitness Centers</option>
          <option value="coaching">🎓 Coaching Academies</option>
          <option value="retail">🛍️ Retail & Supermarkets</option>
        </select>
      </div>

      <div class="form-group" style="margin-bottom:16px;">
        <label class="form-label">3. Lead Discovery Source</label>
        <select id="disc-provider" class="form-select">
          <option value="google_places">🗺️ Google Places API (100% Real Verified Google Maps Data)</option>
          <option value="live">⚡ Live Search & OpenStreetMap (Real Public Leads)</option>
          <option value="sample">🧪 Sample Preset Fixtures (Testing Mode)</option>
        </select>
      </div>

      <div class="form-group" style="margin-bottom:24px;">
        <label class="form-label">4. Max Leads to Ingest</label>
        <select id="disc-limit" class="form-select">
          <option value="3">3 Leads</option>
          <option value="5">5 Leads</option>
          <option value="10" selected>10 Leads</option>
          <option value="15">15 Leads</option>
        </select>
      </div>

      <button class="btn btn-primary" style="width:100%; padding:14px; font-size:14px; font-weight:700; justify-content:center;" onclick="executeLiveDiscovery()">
        🚀 Start Live Discovery & Generate 3-Page Website Demos
      </button>
    </div>
  </div>

  <!-- App Body -->
  <div id="app-body">

    <!-- Left Sidebar: Leads List -->
    <div id="sidebar">
      <div class="sidebar-header">
        <span style="font-weight:700;font-size:12px;text-transform:uppercase;color:var(--text-muted);">Discovered Leads</span>
        <span id="lead-count" class="badge badge-discovered">0 Leads</span>
      </div>
      <div class="filter-group">
        <button class="filter-chip active" onclick="filterLeads('all', this)">All</button>
        <button class="filter-chip" onclick="filterLeads('discovered', this)">Discovered</button>
        <button class="filter-chip" onclick="filterLeads('outreach_ready', this)">Outreach Ready</button>
        <button class="filter-chip" onclick="filterLeads('approved', this)">Approved</button>
        <button class="filter-chip" onclick="filterLeads('sent', this)">Sent</button>
        <button class="filter-chip" onclick="filterLeads('replied', this)">Replied</button>
      </div>
      <ul id="leads-list">
        <!-- Injected via JS -->
      </ul>
    </div>

    <!-- Main View Content Area -->
    <div id="main-content">

      <!-- TAB 1: Lead Studio -->
      <div id="tab-studio" class="tab-view active">
        <div id="no-lead-selected" style="text-align:center;padding:60px 20px;color:var(--text-muted);">
          <h3>Select a business from the left sidebar to inspect discovery, opportunity score, tailored interactive demo, and draft outreach.</h3>
        </div>

        <div id="lead-studio-view" style="display:none; flex-direction: column; gap: 16px;">

          <!-- Pipeline Progression Stepper -->
          <div class="stepper-bar">
            <div id="step-discovered" class="step-node"><span class="step-num">1</span> Discovered</div>
            <span class="step-arrow">➔</span>
            <div id="step-researched" class="step-node"><span class="step-num">2</span> Researched</div>
            <span class="step-arrow">➔</span>
            <div id="step-scored" class="step-node"><span class="step-num">3</span> Opportunity Scored</div>
            <span class="step-arrow">➔</span>
            <div id="step-demo" class="step-node"><span class="step-num">4</span> Demo Generated</div>
            <span class="step-arrow">➔</span>
            <div id="step-outreach" class="step-node"><span class="step-num">5</span> Outreach Drafted</div>
            <span class="step-arrow">➔</span>
            <div id="step-approved" class="step-node"><span class="step-num">6</span> Approved</div>
            <span class="step-arrow">➔</span>
            <div id="step-sent" class="step-node"><span class="step-num">7</span> Dispatched</div>
            <span class="step-arrow">➔</span>
            <div id="step-replied" class="step-node"><span class="step-num">8</span> Replied</div>
          </div>

          <!-- 3-Column Studio Grid -->
          <div class="studio-grid">

            <!-- Column 1: Business Identity & Verified Research -->
            <div class="card">
              <div class="card-title">
                <span>Business & Research Dossier</span>
                <span id="lead-status-badge" class="badge badge-discovered">Status</span>
              </div>

              <div>
                <h2 id="lead-name" style="font-size:17px;font-weight:700;color:var(--text);">Business Name</h2>
                <div id="lead-category-city" style="font-size:12px;color:var(--accent);margin-top:2px;">Category • City</div>
                <div id="lead-website" style="font-size:11.5px;color:var(--text-muted);margin-top:3px;">Website</div>
                <div id="lead-phone-email" style="font-size:11.5px;color:var(--text-muted);margin-top:2px;">Phone • Email</div>
                <div id="lead-source-tag" style="margin-top:6px;"><span class="badge" style="background:#1e293b;color:#cbd5e1;">CSV Ingested Lead</span></div>
              </div>

              <div>
                <div class="form-label" style="margin-bottom:6px;">Verified Evidence Claims</div>
                <div id="evidence-container" style="max-height:200px;overflow-y:auto;">
                  <!-- Evidence injected via JS -->
                </div>
              </div>

              <div>
                <div class="form-label" style="margin-bottom:4px;">Identified Operational Gaps</div>
                <ul id="weaknesses-list" style="font-size:11.5px;color:#fca5a5;padding-left:18px;">
                </ul>
              </div>
            </div>

            <!-- Column 2: Opportunity & Interactive Prototype Demo -->
            <div class="card">
              <div class="card-title">
                <span>Opportunity & Interactive Demo</span>
                <span id="opp-confidence-badge" class="badge badge-scored">High Confidence</span>
              </div>

              <div class="score-banner">
                <div>
                  <div style="font-size:11px;font-weight:600;text-transform:uppercase;color:var(--text-muted);">Opportunity Score</div>
                  <div id="opp-score-val" class="score-number">88 / 100</div>
                </div>
                <div id="opp-type-badge" class="badge badge-demo_ready">Online Booking</div>
              </div>

              <div>
                <div id="opp-problem" style="font-size:12px;color:#fca5a5;margin-bottom:4px;line-height:1.4;">Problem: -</div>
                <div id="opp-solution" style="font-size:12px;color:#86efac;line-height:1.4;">Proposed Solution: -</div>
              </div>

              <div>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                  <div class="form-label">Client-Tailored Interactive Prototype</div>
                  <a id="open-demo-btn" href="#" target="_blank" class="btn btn-outline" style="padding:2px 8px;font-size:11px;">Open Full Prototype ↗</a>
                </div>
                <div class="demo-frame-container">
                  <iframe id="demo-iframe" class="demo-frame" src="about:blank"></iframe>
                </div>
              </div>
            </div>

            <!-- Column 3: Personalized Outreach Email & Approval Gate -->
            <div class="card">
              <div class="card-title">
                <span>Personalized Outreach</span>
                <span id="outreach-approval-badge" class="badge badge-pending_review">Pending Review</span>
              </div>

              <div class="form-group">
                <label class="form-label">Prospect Recipient Email</label>
                <input id="edit-recipient-email" class="form-input" type="email" placeholder="Enter target prospect email address...">
              </div>

              <div class="form-group">
                <label class="form-label">Subject Line</label>
                <input id="edit-subject" class="form-input" type="text">
              </div>

              <div class="form-group">
                <label class="form-label">Personalized Email Body</label>
                <textarea id="edit-body" class="form-textarea" rows="8"></textarea>
              </div>

              <div class="form-group">
                <label class="form-label">Follow-up Cadence Preview (Day 3 & Day 7)</label>
                <div id="followup-preview" style="background:rgba(0,0,0,0.25);border:1px solid var(--border);border-radius:6px;padding:8px;font-size:11px;color:var(--text-muted);max-height:70px;overflow-y:auto;">
                </div>
              </div>

              <!-- Safe Test Override Box -->
              <div style="background:rgba(56,189,248,0.06);border:1px dashed var(--accent);border-radius:6px;padding:8px 10px;">
                <label class="form-label" style="color:var(--accent);">Safe Test Recipient Override (Optional)</label>
                <input id="test-override-email" class="form-input" type="email" placeholder="owner-test-email@example.com" style="margin-top:2px;">
                <div style="font-size:10px;color:var(--text-muted);margin-top:2px;">Enter your own email to safely test real delivery without emailing the prospect.</div>
              </div>

              <!-- Action Controls -->
              <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:4px;">
                <button class="btn btn-outline" onclick="saveEmailChanges()">💾 Save Changes</button>
                <button id="btn-approve" class="btn btn-success" onclick="approveOutreach()">✓ Approve Draft</button>
                <button id="btn-reject" class="btn btn-danger" onclick="rejectOutreach()">✗ Reject</button>
                <button id="btn-send" class="btn btn-primary" onclick="executeSend()">🚀 Dispatch Email</button>
              </div>

              <div id="send-receipt" style="display:none;background:rgba(16,185,129,0.1);border:1px solid var(--green);border-radius:6px;padding:10px;font-size:11.5px;">
              </div>
            </div>

          </div>

        </div>
      </div>

      <!-- TAB 2: Response & Follow-up Center -->
      <div id="tab-responses" class="tab-view">
        <div class="stats-row">
          <div class="stat-card">
            <div class="stat-lbl">Inbound Responses</div>
            <div id="stat-responses-count" class="stat-val">0</div>
          </div>
          <div class="stat-card">
            <div class="stat-lbl">Interested / Meetings</div>
            <div id="stat-interested-count" class="stat-val" style="color:var(--green);">0</div>
          </div>
          <div class="stat-card">
            <div class="stat-lbl">Suppressed / Opt-Outs</div>
            <div id="stat-optout-count" class="stat-val" style="color:var(--red);">0</div>
          </div>
          <div class="stat-card">
            <div class="stat-lbl">Active Follow-up Plans</div>
            <div id="stat-followups-count" class="stat-val" style="color:var(--purple);">0</div>
          </div>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:18px;">
          <!-- Simulator Box -->
          <div class="card">
            <div class="card-title">Simulate Inbound Customer Reply</div>
            <div class="form-group">
              <label class="form-label">Select Sent Outreach Thread</label>
              <select id="sim-outreach-select" class="form-select"></select>
            </div>
            <div class="form-group">
              <label class="form-label">Customer Reply Scenario Templates</label>
              <div style="display:flex;gap:5px;margin-bottom:6px;flex-wrap:wrap;">
                <button class="btn btn-outline" style="font-size:10px;padding:2px 6px;" onclick="setReplyTemplate('Yes, we would love to see the live booking demo. Are you free tomorrow at 3 PM?')">Interested / Meeting Request</button>
                <button class="btn btn-outline" style="font-size:10px;padding:2px 6px;" onclick="setReplyTemplate('What is the approximate monthly cost for this system?')">Pricing Inquiry</button>
                <button class="btn btn-outline" style="font-size:10px;padding:2px 6px;" onclick="setReplyTemplate('Please unsubscribe me and do not contact again.')">Unsubscribe (Opt-Out)</button>
                <button class="btn btn-outline" style="font-size:10px;padding:2px 6px;" onclick="setReplyTemplate('Wrong contact. Please contact info@ management directly.')">Wrong Contact</button>
              </div>
              <textarea id="sim-reply-text" class="form-textarea" rows="3" placeholder="Enter customer reply..."></textarea>
            </div>
            <button class="btn btn-primary" onclick="simulateInboundResponse()">🤖 Ingest & Classify Reply</button>
          </div>

          <!-- Staged Follow-ups Box -->
          <div class="card">
            <div class="card-title">
              <span>Follow-up Cadence Management</span>
              <button class="btn btn-outline" style="font-size:11px;padding:2px 8px;" onclick="stageFollowups()">⚡ Stage Due Follow-ups</button>
            </div>
            <div id="followups-table-container" style="max-height:260px;overflow-y:auto;">
              <!-- Table injected via JS -->
            </div>
          </div>
        </div>

        <!-- Inbound Responses History Table -->
        <div class="card">
          <div class="card-title">Inbound Response Records & Suggested Replies</div>
          <div style="overflow-x:auto;">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Received At</th>
                  <th>Business / Thread</th>
                  <th>AI Classification</th>
                  <th>Inbound Content</th>
                  <th>Suggested AI Reply</th>
                  <th>Follow-up Status</th>
                </tr>
              </thead>
              <tbody id="responses-table-body">
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- TAB 3: Sales Intelligence & Funnel -->
      <div id="tab-analytics" class="tab-view">
        <div class="stats-row">
          <div class="stat-card">
            <div class="stat-lbl">Total Leads Discovered</div>
            <div id="ana-leads" class="stat-val">0</div>
          </div>
          <div class="stat-card">
            <div class="stat-lbl">Qualified Opportunities</div>
            <div id="ana-opps" class="stat-val">0</div>
          </div>
          <div class="stat-card">
            <div class="stat-lbl">Demos Generated</div>
            <div id="ana-demos" class="stat-val">0</div>
          </div>
          <div class="stat-card">
            <div class="stat-lbl">Emails Dispatched</div>
            <div id="ana-sent" class="stat-val" style="color:var(--green);">0</div>
          </div>
          <div class="stat-card">
            <div class="stat-lbl">Response Rate</div>
            <div id="ana-rate" class="stat-val" style="color:var(--purple);">0%</div>
          </div>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:18px;">
          <div class="card">
            <div class="card-title">Sales Conversion Funnel</div>
            <div style="display:flex;flex-direction:column;gap:8px;font-size:12px;margin-top:6px;">
              <div style="display:flex;justify-content:space-between;"><span>1. Discovered Leads</span><strong id="fnl-leads">0</strong></div>
              <div style="display:flex;justify-content:space-between;"><span>2. Researched Dossiers</span><strong id="fnl-researched">0</strong></div>
              <div style="display:flex;justify-content:space-between;"><span>3. Qualified Opportunities</span><strong id="fnl-opps">0</strong></div>
              <div style="display:flex;justify-content:space-between;"><span>4. Tailored Demos Built</span><strong id="fnl-demos">0</strong></div>
              <div style="display:flex;justify-content:space-between;"><span>5. Human Approved Outreach</span><strong id="fnl-approved">0</strong></div>
              <div style="display:flex;justify-content:space-between;"><span>6. Dispatched Emails</span><strong id="fnl-sent">0</strong></div>
              <div style="display:flex;justify-content:space-between;"><span>7. Inbound Responses</span><strong id="fnl-replies">0</strong></div>
              <div style="display:flex;justify-content:space-between;color:var(--green);font-weight:700;"><span>8. Positive Interest / Meetings</span><strong id="fnl-meetings">0</strong></div>
            </div>
          </div>

          <div class="card">
            <div class="card-title">
              <span>Conservative Learning Engine</span>
              <button class="btn btn-outline" style="font-size:11px;padding:2px 8px;" onclick="runFeedbackLearning()">⚡ Recompute Weights</button>
            </div>
            <div id="feedback-report-box" style="font-size:12px;line-height:1.6;color:var(--text-muted);margin-top:6px;">
              <div><strong>Status:</strong> Feedback learning requires &ge; 5 real prospect outcomes before adjusting score weights.</div>
              <div style="margin-top:4px;">Seeded fixture runs are kept separate from real production conversion data.</div>
            </div>
          </div>
        </div>
      </div>

    </div>
  </div>

  <div id="toast">Toast Notification</div>

  <script>
    let allLeads = [];
    let selectedLeadId = null;
    let selectedLeadBundle = null;
    let currentFilter = 'all';
    let isLiveSendMode = false;

    function showToast(msg) {
      const t = document.getElementById('toast');
      t.innerText = msg;
      t.style.display = 'block';
      setTimeout(() => { t.style.display = 'none'; }, 3500);
    }

    function toggleSendMode() {
      isLiveSendMode = !isLiveSendMode;
      const pill = document.getElementById('modePill');
      const text = document.getElementById('modeText');
      if (isLiveSendMode) {
        pill.className = 'mode-pill real';
        text.innerText = 'REAL EMAIL (Live SMTP Dispatch)';
        showToast('Switched to REAL EMAIL mode. Real dispatch requires valid SMTP credentials.');
      } else {
        pill.className = 'mode-pill';
        text.innerText = 'MOCK / DRY-RUN (Safe Audit Mode)';
        showToast('Switched to DRY-RUN mode. Actions are safely audited to output/outreach_staged/.');
      }
    }

    function switchTab(tabId) {
      document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-view').forEach(v => v.classList.remove('active'));
      event.target.classList.add('active');
      document.getElementById('tab-' + tabId).classList.add('active');
      if (tabId === 'responses') loadResponsesAndFollowups();
      if (tabId === 'analytics') loadAnalytics();
    }

    function filterLeads(status, el) {
      currentFilter = status;
      document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
      el.classList.add('active');
      renderLeads();
    }

    async function loadLeads() {
      try {
        const res = await fetch('/api/b2b/leads');
        allLeads = await res.json();
        renderLeads();
        if (allLeads.length > 0 && !selectedLeadId) {
          selectLead(allLeads[0].id);
        }
      } catch (err) {
        console.error('Failed to load leads:', err);
      }
    }

    function renderLeads() {
      const listEl = document.getElementById('leads-list');
      listEl.innerHTML = '';
      const filtered = currentFilter === 'all' ? allLeads : allLeads.filter(l => l.status === currentFilter);
      document.getElementById('lead-count').innerText = `${filtered.length} Leads`;

      filtered.forEach(lead => {
        const li = document.createElement('li');
        li.className = `lead-item ${lead.id === selectedLeadId ? 'selected' : ''}`;
        li.onclick = () => selectLead(lead.id);
        li.innerHTML = `
          <div class="lead-title">${escapeHtml(lead.name)}</div>
          <div class="lead-sub">
            <span>${escapeHtml(lead.category)} • ${escapeHtml(lead.city)}</span>
            <span class="badge badge-${lead.status}">${lead.status}</span>
          </div>
        `;
        listEl.appendChild(li);
      });
    }

    async function selectLead(leadId) {
      selectedLeadId = leadId;
      renderLeads();
      document.getElementById('no-lead-selected').style.display = 'none';
      const studioView = document.getElementById('lead-studio-view');
      studioView.style.display = 'flex';

      try {
        const res = await fetch(`/api/b2b/leads/${leadId}`);
        const bundle = await res.json();
        selectedLeadBundle = bundle;
        renderLeadBundle(bundle);
      } catch (err) {
        console.error('Failed to load lead bundle:', err);
      }
    }

    function renderLeadBundle(b) {
      const biz = b.business;
      document.getElementById('lead-name').innerText = biz.name;
      document.getElementById('lead-category-city').innerText = `${biz.category.toUpperCase()} • ${biz.city}, ${biz.state || 'India'}`;
      document.getElementById('lead-website').innerText = biz.website ? `🌐 ${biz.website}` : '🌐 No official website listed';
      document.getElementById('lead-phone-email').innerText = `📞 ${biz.phone || 'Phone unlisted'} • ✉️ ${biz.email || 'Email unlisted'}`;
      document.getElementById('lead-status-badge').className = `badge badge-${biz.status}`;
      document.getElementById('lead-status-badge').innerText = biz.status;

      // Update Stepper
      updateStepper(biz.status, b.outreach, b.demos);

      // Evidence
      const evCont = document.getElementById('evidence-container');
      evCont.innerHTML = '';
      const evidence = (b.research && b.research.evidence) ? b.research.evidence : [];
      if (evidence.length === 0) {
        evCont.innerHTML = '<div style="font-size:11.5px;color:var(--text-muted);">No evidence claims recorded yet.</div>';
      } else {
        evidence.forEach(ev => {
          const div = document.createElement('div');
          const typeClass = ev.claim_type === 'verified_fact' ? 'fact' : (ev.claim_type === 'ai_inference' ? 'inference' : 'unknown');
          div.className = `evidence-item ${typeClass}`;
          div.innerHTML = `
            <div style="display:flex;justify-content:space-between;color:var(--text-muted);font-size:10px;margin-bottom:2px;">
              <span>${ev.category.toUpperCase()}</span>
              <span>${ev.claim_type} (${Math.round(ev.confidence * 100)}%)</span>
            </div>
            <div>${escapeHtml(ev.claim)}</div>
          `;
          evCont.appendChild(div);
        });
      }

      // Weaknesses
      const wList = document.getElementById('weaknesses-list');
      wList.innerHTML = '';
      const weaknesses = (b.research && b.research.observed_weaknesses) ? b.research.observed_weaknesses : [];
      if (weaknesses.length === 0) {
        wList.innerHTML = '<li>None identified</li>';
      } else {
        weaknesses.forEach(w => {
          const li = document.createElement('li');
          li.innerText = w;
          wList.appendChild(li);
        });
      }

      // Opportunity
      const opp = b.opportunities && b.opportunities.length > 0 ? b.opportunities[0] : null;
      if (opp) {
        document.getElementById('opp-score-val').innerText = `${Math.round(opp.score)} / 100`;
        document.getElementById('opp-confidence-badge').innerText = opp.score >= 70 ? 'High Confidence' : 'Moderate Confidence';
        document.getElementById('opp-type-badge').innerText = opp.opportunity_type.replace(/_/g, ' ').toUpperCase();
        document.getElementById('opp-problem').innerText = `• Problem: ${opp.problem_summary}`;
        document.getElementById('opp-solution').innerText = `• Solution: ${opp.proposed_solution}`;
      } else {
        document.getElementById('opp-score-val').innerText = '- / 100';
        document.getElementById('opp-confidence-badge').innerText = 'Low Confidence / Insufficient Data';
        document.getElementById('opp-problem').innerText = 'No opportunity analyzed yet.';
        document.getElementById('opp-solution').innerText = '';
      }

      // Demo
      const demo = b.demos && b.demos.length > 0 ? b.demos[0] : null;
      const iframe = document.getElementById('demo-iframe');
      const openDemoBtn = document.getElementById('open-demo-btn');
      if (demo) {
        const previewUrl = `/demos/${demo.id}/index.html`;
        iframe.src = previewUrl;
        openDemoBtn.href = previewUrl;
        openDemoBtn.style.display = 'inline-flex';
      } else {
        iframe.src = 'about:blank';
        openDemoBtn.style.display = 'none';
      }

      // Outreach
      const out = b.outreach && b.outreach.length > 0 ? b.outreach[0] : null;
      if (out) {
        document.getElementById('edit-recipient-email').value = out.recipient_email || '';
        document.getElementById('edit-subject').value = out.subject || '';
        document.getElementById('edit-body').value = out.body_text || '';
        document.getElementById('outreach-approval-badge').className = `badge badge-${out.approval_status}`;
        document.getElementById('outreach-approval-badge').innerText = out.approval_status;
        document.getElementById('followup-preview').innerText = out.followup_body || 'Standard Day 3 and Day 7 follow-up sequences configured.';

        if (out.send_status === 'sent') {
          document.getElementById('send-receipt').style.display = 'block';
          document.getElementById('send-receipt').innerHTML = `
            <strong>✓ Dispatched:</strong> Sent at ${out.sent_at || '-'} (Message ID: ${out.provider_message_id || 'mock_payload'})
          `;
        } else {
          document.getElementById('send-receipt').style.display = 'none';
        }
      } else {
        document.getElementById('edit-recipient-email').value = biz.email || '';
        document.getElementById('edit-subject').value = '';
        document.getElementById('edit-body').value = '';
        document.getElementById('outreach-approval-badge').innerText = 'No Draft';
        document.getElementById('send-receipt').style.display = 'none';
      }
    }

    function updateStepper(status, outreach, demos) {
      const steps = ['discovered', 'researched', 'scored', 'demo', 'outreach', 'approved', 'sent', 'replied'];
      steps.forEach(s => {
        const node = document.getElementById('step-' + s);
        if (node) node.className = 'step-node';
      });

      document.getElementById('step-discovered').classList.add('completed');
      if (status !== 'discovered') document.getElementById('step-researched').classList.add('completed');
      if (status === 'scored' || status === 'demo_ready' || status === 'outreach_ready' || status === 'approved' || status === 'sent' || status === 'replied') {
        document.getElementById('step-scored').classList.add('completed');
      }
      if (demos && demos.length > 0) document.getElementById('step-demo').classList.add('completed');
      if (outreach && outreach.length > 0) {
        document.getElementById('step-outreach').classList.add('completed');
        if (outreach[0].approval_status === 'approved') document.getElementById('step-approved').classList.add('completed');
        if (outreach[0].send_status === 'sent') document.getElementById('step-sent').classList.add('completed');
      }
      if (status === 'replied') document.getElementById('step-replied').classList.add('completed');
    }

    async function saveEmailChanges() {
      if (!selectedLeadBundle || !selectedLeadBundle.outreach || selectedLeadBundle.outreach.length === 0) return;
      const outId = selectedLeadBundle.outreach[0].id;
      const payload = {
        recipient_email: document.getElementById('edit-recipient-email').value,
        subject: document.getElementById('edit-subject').value,
        body_text: document.getElementById('edit-body').value,
      };
      const res = await fetch(`/api/b2b/outreach/${outId}/edit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        showToast('Outreach draft saved successfully!');
        selectLead(selectedLeadId);
      }
    }

    async function approveOutreach() {
      if (!selectedLeadBundle || !selectedLeadBundle.outreach || selectedLeadBundle.outreach.length === 0) return;
      const outId = selectedLeadBundle.outreach[0].id;
      const res = await fetch(`/api/b2b/outreach/${outId}/approve`, { method: 'POST' });
      if (res.ok) {
        showToast('Outreach Approved for Sending!');
        selectLead(selectedLeadId);
        loadLeads();
      }
    }

    async function rejectOutreach() {
      if (!selectedLeadBundle || !selectedLeadBundle.outreach || selectedLeadBundle.outreach.length === 0) return;
      const outId = selectedLeadBundle.outreach[0].id;
      const res = await fetch(`/api/b2b/outreach/${outId}/reject`, { method: 'POST' });
      if (res.ok) {
        showToast('Outreach Rejected.');
        selectLead(selectedLeadId);
        loadLeads();
      }
    }

    async function executeSend() {
      if (!selectedLeadBundle || !selectedLeadBundle.outreach || selectedLeadBundle.outreach.length === 0) return;
      const outId = selectedLeadBundle.outreach[0].id;
      const overrideEmail = document.getElementById('test-override-email').value.trim();

      const payload = {
        force_dry_run: !isLiveSendMode,
        override_recipient: overrideEmail || null,
      };

      const res = await fetch(`/api/b2b/outreach/${outId}/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok) {
        const modeDesc = isLiveSendMode ? 'Live SMTP Dispatched' : 'Dry-Run Simulation Staged';
        showToast(`Email Dispatched! (${modeDesc})`);
        selectLead(selectedLeadId);
        loadLeads();
      } else {
        alert(`Sending Blocked: ${data.error || 'Approval gate check failed'}`);
      }
    }

    function openDiscoveryModal() {
      document.getElementById('discoveryModal').style.display = 'flex';
    }

    function closeDiscoveryModal() {
      document.getElementById('discoveryModal').style.display = 'none';
    }

    async function executeLiveDiscovery() {
      const city = document.getElementById('disc-city').value.trim() || 'Ahmedabad';
      const category = document.getElementById('disc-category').value;
      const provider = document.getElementById('disc-provider').value;
      const limit = parseInt(document.getElementById('disc-limit').value, 10);

      closeDiscoveryModal();
      showToast(`Searching '${category}' in '${city}'... Running AI research & generating 3-page website prototypes.`);

      try {
        const res = await fetch('/api/b2b/pipeline/run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ city, category, provider, limit })
        });
        const data = await res.json();
        showToast(`Discovery complete! ${data.businesses_count || 0} leads saved, ${data.demos_count || 0} 3-page website demos ready.`);
        loadLeads();
      } catch (err) {
        showToast('Error during discovery execution: ' + err.message);
      }
    }

    async function loadResponsesAndFollowups() {
      try {
        const [respRes, fuRes, outRes] = await Promise.all([
          fetch('/api/b2b/responses'),
          fetch('/api/b2b/followups'),
          fetch('/api/b2b/outreach')
        ]);
        const responses = await respRes.json();
        const followups = await fuRes.json();
        const outreaches = await outRes.json();

        document.getElementById('stat-responses-count').innerText = responses.length;
        document.getElementById('stat-interested-count').innerText = responses.filter(r => r.classification === 'interested' || r.classification === 'wants_meeting').length;
        document.getElementById('stat-optout-count').innerText = responses.filter(r => r.classification === 'unsubscribed' || r.classification === 'wrong_contact').length;
        document.getElementById('stat-followups-count').innerText = followups.length;

        // Populate sim select
        const sel = document.getElementById('sim-outreach-select');
        sel.innerHTML = '';
        outreaches.forEach(o => {
          const opt = document.createElement('option');
          opt.value = o.id;
          opt.innerText = `${o.subject} (${o.recipient_email}) [${o.send_status}]`;
          sel.appendChild(opt);
        });

        // Populate responses table
        const tbody = document.getElementById('responses-table-body');
        tbody.innerHTML = '';
        responses.forEach(r => {
          const tr = document.createElement('tr');
          const isTerminal = r.classification === 'unsubscribed' || r.classification === 'wrong_contact';
          tr.innerHTML = `
            <td style="color:var(--text-muted);font-size:11px;">${r.received_at.substring(0,19).replace('T',' ')}</td>
            <td style="font-weight:600;">${escapeHtml(r.business_id)}</td>
            <td><span class="badge badge-${isTerminal ? 'suppressed' : 'replied'}">${r.classification}</span></td>
            <td>${escapeHtml(r.raw_content)}</td>
            <td style="color:#86efac;font-size:11.5px;">${escapeHtml(r.suggested_reply || '-')}</td>
            <td><span class="badge ${isTerminal ? 'badge-suppressed' : 'badge-approved'}">${isTerminal ? '🛑 Opt-out Suppressed' : 'Active'}</span></td>
          `;
          tbody.appendChild(tr);
        });

        // Populate followups
        const fuCont = document.getElementById('followups-table-container');
        if (followups.length === 0) {
          fuCont.innerHTML = '<div style="color:var(--text-muted);padding:14px;font-size:12px;">No active follow-ups staged yet.</div>';
        } else {
          let html = '<table class="data-table"><thead><tr><th>Step</th><th>Subject</th><th>Status</th><th>Action</th></tr></thead><tbody>';
          followups.forEach(f => {
            html += `
              <tr>
                <td>Day ${f.step_number === 1 ? '3' : '7'}</td>
                <td>${escapeHtml(f.subject)}</td>
                <td><span class="badge badge-${f.status}">${f.status}</span></td>
                <td>
                  ${f.status === 'pending_review' ? `<button class="btn btn-outline" style="padding:2px 6px;font-size:10px;" onclick="approveFollowup('${f.id}')">Approve</button>` : ''}
                  ${f.status === 'approved' ? `<button class="btn btn-primary" style="padding:2px 6px;font-size:10px;" onclick="sendFollowup('${f.id}')">Send</button>` : ''}
                  ${f.status === 'suppressed' ? `<span style="color:#fca5a5;font-size:10px;">Opt-Out Enforced</span>` : ''}
                </td>
              </tr>
            `;
          });
          html += '</tbody></table>';
          fuCont.innerHTML = html;
        }

      } catch (err) {
        console.error('Failed loading responses/followups:', err);
      }
    }

    function setReplyTemplate(text) {
      document.getElementById('sim-reply-text').value = text;
    }

    async function simulateInboundResponse() {
      const outreachId = document.getElementById('sim-outreach-select').value;
      const message = document.getElementById('sim-reply-text').value;
      if (!outreachId || !message) {
        alert('Please select an outreach thread and enter reply text.');
        return;
      }
      const res = await fetch(`/api/b2b/outreach/${outreachId}/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message })
      });
      const data = await res.json();
      if (res.ok) {
        showToast(`Reply ingested and classified as '${data.classification}'!`);
        document.getElementById('sim-reply-text').value = '';
        loadResponsesAndFollowups();
        loadLeads();
      }
    }

    async function stageFollowups() {
      const res = await fetch('/api/b2b/followups/stage', { method: 'POST' });
      const data = await res.json();
      showToast(`Staged ${data.staged_count || 0} due follow-up records.`);
      loadResponsesAndFollowups();
    }

    async function approveFollowup(id) {
      await fetch(`/api/b2b/followups/${id}/approve`, { method: 'POST' });
      showToast('Follow-up approved.');
      loadResponsesAndFollowups();
    }

    async function sendFollowup(id) {
      await fetch(`/api/b2b/followups/${id}/send`, { method: 'POST' });
      showToast('Follow-up dispatched!');
      loadResponsesAndFollowups();
    }

    async function loadAnalytics() {
      const res = await fetch('/api/b2b/stats');
      const stats = await res.json();
      document.getElementById('ana-leads').innerText = stats.total_leads || 0;
      document.getElementById('ana-opps').innerText = stats.total_opportunities || 0;
      document.getElementById('ana-demos').innerText = stats.total_demos || 0;
      document.getElementById('ana-sent').innerText = stats.total_sent || 0;
      const rate = stats.total_sent > 0 ? Math.round((stats.total_responses / stats.total_sent) * 100) : 0;
      document.getElementById('ana-rate').innerText = `${rate}%`;

      document.getElementById('fnl-leads').innerText = stats.total_leads || 0;
      document.getElementById('fnl-researched').innerText = stats.total_leads || 0;
      document.getElementById('fnl-opps').innerText = stats.total_opportunities || 0;
      document.getElementById('fnl-demos').innerText = stats.total_demos || 0;
      document.getElementById('fnl-approved').innerText = stats.total_outreach || 0;
      document.getElementById('fnl-sent').innerText = stats.total_sent || 0;
      document.getElementById('fnl-replies').innerText = stats.total_responses || 0;
      document.getElementById('fnl-meetings').innerText = stats.total_responses || 0;
    }

    async function runFeedbackLearning() {
      const res = await fetch('/api/b2b/feedback/run', { method: 'POST' });
      const data = await res.json();
      document.getElementById('feedback-report-box').innerHTML = `
        <div style="color:var(--accent);font-weight:700;">✓ Optimization Check Complete</div>
        <div><strong>Total Samples:</strong> ${data.totals_sent || 0} sent conversations observed.</div>
        <div>${data.neutral_note || 'Conservative baseline maintained.'}</div>
      `;
      showToast('Feedback analysis complete.');
    }

    function escapeHtml(str) {
      if (!str) return '';
      return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    // Init on page load
    loadLeads();
  </script>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, db: Database | None = None, **kwargs) -> None:
        self.db = db or Database()
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            self._send_html(DASHBOARD_HTML)
            return

        # --- B2B JSON Endpoints ---
        if path == "/api/b2b/stats":
            leads = self.db.list_businesses(limit=1000)
            opps = self.db.list_opportunities(limit=1000)
            demos = self.db.list_demos(limit=1000)
            outreaches = self.db.list_outreach(limit=1000)
            responses = self.db.list_outreach_responses(limit=1000)
            sent_count = len([o for o in outreaches if o.send_status == SendStatus.SENT])

            self._send_json({
                "total_leads": len(leads),
                "total_opportunities": len(opps),
                "total_demos": len(demos),
                "total_outreach": len(outreaches),
                "total_sent": sent_count,
                "total_responses": len(responses),
            })
            return

        if path == "/api/b2b/leads":
            leads = self.db.list_businesses(limit=100)
            self._send_json([l.model_dump(mode="json") for l in leads])
            return

        if path.startswith("/api/b2b/leads/"):
            biz_id = path.split("/api/b2b/leads/")[1]
            biz = self.db.get_business(biz_id)
            if not biz:
                self._send_error(HTTPStatus.NOT_FOUND, f"Business not found: {biz_id}")
                return
            research = self.db.get_business_research(biz_id)
            opps = self.db.list_opportunities(business_id=biz_id)
            demos = self.db.list_demos(business_id=biz_id)
            outreaches = self.db.list_outreach(business_id=biz_id)
            responses = self.db.list_outreach_responses(business_id=biz_id)
            followups = self.db.list_followups(business_id=biz_id)

            bundle = {
                "business": biz.model_dump(mode="json"),
                "research": research.model_dump(mode="json") if research else None,
                "opportunities": [o.model_dump(mode="json") for o in opps],
                "demos": [d.model_dump(mode="json") for d in demos],
                "outreach": [o.model_dump(mode="json") for o in outreaches],
                "responses": [r.model_dump(mode="json") for r in responses],
                "followups": [f.model_dump(mode="json") for f in followups],
            }
            self._send_json(bundle)
            return

        if path == "/api/b2b/opportunities":
            opps = self.db.list_opportunities(limit=100)
            self._send_json([o.model_dump(mode="json") for o in opps])
            return

        if path == "/api/b2b/demos":
            demos = self.db.list_demos(limit=100)
            self._send_json([d.model_dump(mode="json") for d in demos])
            return

        if path == "/api/b2b/outreach":
            outreaches = self.db.list_outreach(limit=100)
            self._send_json([o.model_dump(mode="json") for o in outreaches])
            return

        if path == "/api/b2b/responses":
            responses = self.db.list_outreach_responses(limit=100)
            self._send_json([r.model_dump(mode="json") for r in responses])
            return

        if path == "/api/b2b/followups":
            followups = self.db.list_followups(limit=100)
            self._send_json([f.model_dump(mode="json") for f in followups])
            return

        # --- Legacy Content Automation Endpoints ---
        if path == "/api/jobs":
            jobs = self.db.list_jobs()
            self._send_json([j.model_dump(mode="json") for j in jobs])
            return

        if path == "/api/analytics/summary":
            reporter = AnalyticsReporter(db=self.db)
            report = reporter.generate_summary_report()
            self._send_json(report.model_dump(mode="json"))
            return

        if path == "/api/analytics/insights":
            engine = PerformanceInsightsEngine(db=self.db)
            report = engine.generate_insights()
            self._send_json(report.model_dump(mode="json"))
            return

        if path == "/api/health":
            monitor = SystemHealthMonitor(db=self.db)
            self._send_json(monitor.check_health())
            return

        if path == "/api/audit":
            records = self.db.list_audit_logs(limit=50)
            self._send_json([r.model_dump(mode="json") for r in records])
            return

        if path == "/api/safeguards":
            quota_guard = PublishQuotaGuard(db=self.db)
            self._send_json({"quota": quota_guard.get_quota_status()})
            return

        if path.startswith("/api/jobs/") and path.endswith("/analytics"):
            job_id = path.split("/api/jobs/")[1].split("/analytics")[0]
            snapshots = self.db.list_snapshots(job_id=job_id)
            self._send_json([s.model_dump(mode="json") for s in snapshots])
            return

        if path.startswith("/api/jobs/"):
            job_id = path.split("/api/jobs/")[1]
            job = self.db.get_job(job_id)
            if job:
                self._send_json(job.model_dump(mode="json"))
            else:
                self._send_error(HTTPStatus.NOT_FOUND, "Job not found")
            return

        # Serve static generated Demos (e.g. /demos/demo_xxx/index.html -> output/demos/demo_xxx/index.html)
        if path.startswith("/demos/"):
            rel = path.lstrip("/")
            file_path = PROJECT_ROOT / "output" / rel
            if file_path.exists() and file_path.is_file():
                self._serve_file(file_path)
                return
            self._send_error(HTTPStatus.NOT_FOUND, f"Demo file not found: {path}")
            return

        # Static files in output/
        if path.startswith("/output/"):
            rel_path = path.lstrip("/")
            file_path = PROJECT_ROOT / rel_path
            if file_path.exists() and file_path.is_file():
                self._serve_file(file_path)
                return
            self._send_error(HTTPStatus.NOT_FOUND, f"File not found: {path}")
            return

        self._send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            data = json.loads(body)
        except Exception:
            data = {}

        # Legacy Job Actions
        if path.endswith("/status") and "/api/jobs/" in path:
            job_id = path.split("/api/jobs/")[1].split("/status")[0]
            new_status = data.get("status", "pending_review")
            notes = data.get("notes")
            updated = self.db.update_status(job_id, new_status, notes=notes)
            if updated:
                self._send_json(updated.model_dump(mode="json"))
            else:
                self._send_error(HTTPStatus.NOT_FOUND, "Job not found")
            return

        if path.endswith("/edit") and "/api/jobs/" in path:
            job_id = path.split("/api/jobs/")[1].split("/edit")[0]
            updated = self.db.update_metadata(
                job_id,
                youtube_title=data.get("youtube_title"),
                youtube_description=data.get("youtube_description"),
                instagram_caption=data.get("instagram_caption"),
                notes=data.get("notes"),
            )
            if updated:
                self._send_json(updated.model_dump(mode="json"))
            else:
                self._send_error(HTTPStatus.NOT_FOUND, "Job not found")
            return

        # 1. Run Pipeline Cycle
        if path == "/api/b2b/pipeline/run":
            limit = int(data.get("limit", 5))
            provider_name = data.get("provider", "live")
            city = data.get("city", "Ahmedabad")
            category = data.get("category", "clinic")

            print("\n" + "=" * 80)
            print(f"🚀 [STARTING B2B ACQUISITION PIPELINE] Location: '{city}' | Category: '{category}' | Limit: {limit}")
            print("=" * 80)

            if provider_name == "sample":
                print("\n📍 [PHASE 1: LEAD DISCOVERY] Loading sample fixture dataset...")
                build_sample_business_dataset(self.db)
                businesses = sample_business_records()[:limit]
                research_list = generate_sample_research()[:limit]
                print(f"  ▶ Phase 1 Complete: Loaded {len(businesses)} sample business leads.")
                print(f"  ▶ Phase 2 Complete: Loaded {len(research_list)} sample research dossiers.")
            else:
                print(f"\n📍 [PHASE 1: LEAD DISCOVERY] Searching live leads for category: '{category}' in city: '{city}'...")
                disc_service = DiscoveryService(db=self.db)
                res = disc_service.ingest_leads(
                    provider_name=provider_name,
                    city=city,
                    category=category,
                    limit=limit,
                )
                businesses = res.businesses
                if not businesses:
                    businesses = self.db.list_businesses(limit=limit)

                print(f"  ▶ Phase 1 Complete: {len(businesses)} business leads active for pipeline.")

                print(f"\n🔬 [PHASE 2: DEEP RESEARCH & ENRICHMENT] Performing deep web research on {len(businesses)} businesses...")
                research_provider = ResearchRegistry.get("http_web") or HTTPWebResearchProvider()
                research_list = []
                for idx, b in enumerate(businesses, 1):
                    r = self.db.get_business_research(b.id)
                    if not r:
                        print(f"  [{idx}/{len(businesses)}] Researching: {b.name} ({b.city})...")
                        r = research_provider.research(b)
                        self.db.save_business_research(r)
                        self.db.update_business_status(b.id, BusinessStatus.RESEARCHED)
                    else:
                        print(f"  [{idx}/{len(businesses)}] Retained Research Dossier: {b.name} ({b.city})...")
                    research_list.append(r)
                    print(f"     ├─ Fact Claims Gathered: {len(r.evidence)} evidence points")
                    print(f"     ├─ Contact Email: {b.email}")
                    print(f"     └─ Phone: {b.phone}")

                print(f"  ▶ Phase 2 Complete: {len(research_list)} research dossiers stored.")

            # Run Intelligence Bundle
            intel = BusinessIntelligenceService(db=self.db)
            ctx = BusinessCycleContext(cycle_id=f"cycle_{uuid.uuid4().hex[:8]}")
            opps = intel.run_analysis_step(ctx, research_list)
            demos = intel.run_demo_step(ctx, opps)
            drafts = intel.run_outreach_step(ctx, demos)

            self._send_json({
                "status": "success",
                "businesses_count": len(businesses),
                "research_count": len(research_list),
                "opportunities_count": len(opps),
                "demos_count": len(demos),
                "outreach_drafts_count": len(drafts),
            })
            return

        # 2. Edit Outreach Draft
        if path.startswith("/api/b2b/outreach/") and path.endswith("/edit"):
            out_id = path.split("/api/b2b/outreach/")[1].split("/edit")[0]
            outreach = self.db.get_outreach(out_id)
            if not outreach:
                self._send_error(HTTPStatus.NOT_FOUND, f"Outreach not found: {out_id}")
                return
            if "subject" in data:
                outreach.subject = data["subject"]
            if "body_text" in data:
                outreach.body_text = data["body_text"]
            if "recipient_email" in data:
                outreach.recipient_email = data["recipient_email"]
            saved = self.db.save_outreach(outreach)
            self._send_json(saved.model_dump(mode="json"))
            return

        # 3. Approve Outreach
        if path.startswith("/api/b2b/outreach/") and path.endswith("/approve"):
            out_id = path.split("/api/b2b/outreach/")[1].split("/approve")[0]
            updated = self.db.update_outreach_approval(out_id, ApprovalStatus.APPROVED)
            if updated:
                self._send_json(updated.model_dump(mode="json"))
            else:
                self._send_error(HTTPStatus.NOT_FOUND, "Outreach not found")
            return

        # 4. Reject Outreach
        if path.startswith("/api/b2b/outreach/") and path.endswith("/reject"):
            out_id = path.split("/api/b2b/outreach/")[1].split("/reject")[0]
            updated = self.db.update_outreach_approval(out_id, ApprovalStatus.REJECTED)
            if updated:
                self._send_json(updated.model_dump(mode="json"))
            else:
                self._send_error(HTTPStatus.NOT_FOUND, "Outreach not found")
            return

        # 5. Send Outreach (Enforces approval gate & safe override)
        if path.startswith("/api/b2b/outreach/") and path.endswith("/send"):
            out_id = path.split("/api/b2b/outreach/")[1].split("/send")[0]
            force_dry_run = bool(data.get("force_dry_run", True))
            override_recipient = data.get("override_recipient")
            sender = OutreachSendingService(db=self.db, live=not force_dry_run)
            try:
                sent_record = sender.send_outreach(
                    out_id,
                    force_dry_run=force_dry_run,
                    override_recipient=override_recipient,
                )
                self._send_json(sent_record.model_dump(mode="json"))
            except ApprovalGateError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            except Exception as exc:
                self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
            return

        # 6. Simulate / Ingest Inbound Response
        if path.startswith("/api/b2b/outreach/") and path.endswith("/respond"):
            out_id = path.split("/api/b2b/outreach/")[1].split("/respond")[0]
            message = data.get("message", "Interested in seeing the demo.")
            intel = BusinessIntelligenceService(db=self.db)
            try:
                resp = intel.ingest_response(None, out_id, message)
                self._send_json(resp.model_dump(mode="json"))
            except Exception as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return

        # 7. Follow-up Operations
        if path == "/api/b2b/followups/stage":
            intel = BusinessIntelligenceService(db=self.db)
            ctx = BusinessCycleContext(cycle_id=f"cycle_{uuid.uuid4().hex[:8]}")
            staged, plans = intel.followup_step(ctx)
            staged, plans = intel.followup_step(ctx)
            self._send_json({
                "staged_count": len(staged),
                "eligible_plans": len([p for p in plans if p.eligible]),
            })
            return

        if path.startswith("/api/b2b/followups/") and path.endswith("/approve"):
            fu_id = path.split("/api/b2b/followups/")[1].split("/approve")[0]
            updated = self.db.update_followup_status(fu_id, FollowUpStatus.APPROVED)
            self._send_json(updated.model_dump(mode="json") if updated else {})
            return

        if path.startswith("/api/b2b/followups/") and path.endswith("/send"):
            fu_id = path.split("/api/b2b/followups/")[1].split("/send")[0]
            sender = OutreachSendingService(db=self.db, live=False)
            try:
                sent_fu = sender.send_followup(fu_id, force_dry_run=True)
                self._send_json(sent_fu.model_dump(mode="json"))
            except Exception as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return

        # 8. Feedback Optimization
        if path == "/api/b2b/feedback/run":
            intel = BusinessIntelligenceService(db=self.db)
            ctx = BusinessCycleContext()
            report = intel.feedback_step(ctx)
            self._send_json(report.api_dict())
            return

        self._send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    # -- helpers -----------------------------------------------------------

    def _send_html(self, html: str) -> None:
        raw = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_json(self, payload: Any, status: int = HTTPStatus.OK) -> None:
        raw = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_error(self, status: int, message: str) -> None:
        self._send_json({"error": message}, status=status)

    def _serve_file(self, file_path: Path) -> None:
        ctype, _ = mimetypes.guess_type(str(file_path))
        ctype = ctype or "application/octet-stream"
        raw = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def run_dashboard_server(
    host: str = "127.0.0.1",
    port: int = 8088,
    db: Database | None = None,
) -> HTTPServer:
    database = db or Database()

    def handler_factory(*args, **kwargs):
        return DashboardHandler(*args, db=database, **kwargs)

    server = HTTPServer((host, port), handler_factory)
    logger.info("B2B Outreach Studio running at http://%s:%d", host, port)
    return server