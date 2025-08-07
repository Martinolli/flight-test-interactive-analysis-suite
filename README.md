# FTIAS Project Description Requirements

## Version 1.0 - 2025-08-07

## 1. Introduction

1.1. Purpose
To develop a secure, scalable, and interactive software suite for flight test data analysis, enabling engineers to visualize, interrogate, and report on test results with flexibility and precision. The tool must support future AI/LLM integration and geospatial visualization.

1.2. Scope
Import, manage, and visualize flight test datasets.

Flexible charting: any parameter on any axis.

Interactive controls: time interval, zoom, annotations.

User management, session save/load, audit logging.

Ready for AI agent and Google Earth integration.

Professional deployment for corporate environments.

1.3. Stakeholders
Flight test engineers, analysts, data scientists.

Project managers.

IT administrators.

## 2. Overall Description

    2.1. Product Perspective
    FTIAS is a web-based application hosted on the company network, accessible to authorized users via browser.
    Future versions will support AI analysis agents and geospatial flight path overlays.

    2.2. User Classes and Characteristics
    User Role Description
    Viewer Can view, explore, and export charts and reports
    Analyst Can upload data, create and save sessions, annotate, generate reports
    Admin User/role management, audit log access, backend configuration

    2.3. Operating Environment
    Web browsers (Chrome, Edge, Firefox)

    Company server (Linux or Windows)

    Dockerized deployment

    2.4. Design/Implementation Constraints
    Use Plotly for charting (via Plotly.js/React or Dash)

    Backend in Python (FastAPI recommended)

    Store data locally or in PostgreSQL/SQLite

    Authentication via LDAP/SSO or JWT

    Modular to support LLM/AI and geospatial upgrades

## 3. System Features and Requirements

    3.1. Core Features (MVP Phase)
    Feature    Description    Priority    Review Point
    Data Import    Upload Excel/CSV/XLSX; parse and validate headers/units    Must    Demo file import, validation check with sample data
    Parameter Browser    List all available parameters with codes/units/descriptions    Must    User can search/browse parameters
    Flexible Charting    User selects X/Y (and optional Z/color) from any parameters    Must    User demo: Plot time vs altitude, then velocity vs altitude
    Interactive Charts    Pan, zoom, hover tooltips, hide/show traces, export chart    Must    Chart features tested with real data
    Time Interval Select    Slider or input to filter visible time window    Must    User sets time range, chart updates instantly
    Data Table View    Preview raw/filtered data, synchronized with chart    Should    Data table shows only selected time window
    Session Save/Load    Save/load chart configs, selected parameters, and filters    Should    Load previous session, restore all state
    Export Data/Charts    Export selected chart as PNG, HTML, CSV    Should    Exported files open correctly
    
    3.2. Security & Corporate Features
    Feature    Description    Priority    Review Point
    User Authentication    SSO/LDAP or JWT login, role-based access    Must    Demo login flow, test with test users
    Audit Logging    Log file uploads, session activity, chart generation    Should    Audit log exports show all key activities
    Data Privacy    Ensure sensitive data is only visible to authorized users    Must    Test with multiple users and permissions
    
    3.3. Future Feature Phases
    A. LLM Agent Integration
    Feature    Description    Priority    Review Point
    LLM Chat Panel    Users can ask questions, request summaries, or get chart suggestions    Could    Demo basic LLM integration with OpenAI (test queries)
    Report Generation    LLM can generate flight summaries, charts, and insight commentary    Could    LLM produces summary on real data
    
    B. Geospatial/Google Earth Integration
    Feature    Description    Priority    Review Point
    KML/KMZ Export    Export trajectory (lat/lon/alt) as Google Earth file    Should    KML opened in Google Earth, flight path matches
    In-App Map Viewer    (Optional) CesiumJS/Kepler.gl for flight path playback    Could    Display and animate flight on map in-app
    
    C. Engineering Utilities
    Feature    Description    Priority    Review Point
    Derived Parameters    User-defined formulas (e.g., TAS - GS, or altitude difference)    Could    User defines, plots new parameter
    Annotation & Notes    Add notes to chart for review/traceability    Could    Save, display annotation; link to session
    Automated Data Checks    Highlight anomalies or data quality issues    Could    Visual or LLM flags for gaps, spikes

## 4. Technical Stack Recommendations

    Component Recommended Tech Notes
    Frontend React.js + Plotly.js Best for interactive, modern web UI; rich Plotly support
    Backend Python + FastAPI Modern, async, great for data processing and LLM APIs
    Data Storage PostgreSQL Robust, scalable, good for metadata/session/user data
    File Storage Local server/NAS Large data files; can integrate with S3 or similar
    Auth LDAP/SSO or JWT Corporate authentication
    Deployment Docker Easy update and rollback
    LLM Integration OpenAI API (v1), local LLM (future) Modular API-based; can switch providers as needed
    Map/3D Viewer CesiumJS or Kepler.gl Optional, for future phase

## 5. Project Phases and Review Points

    Phase Milestone/Review Gate
    1. MVP Core File import, charting, parameter browser, time interval, user auth
    - Review: Demo with real data, user tests all key features
    2. Corporate Deployment Audit logging, role-based permissions, data privacy test
    - Review: Security walkthrough, admin/test user scenarios
    3. Session/Export Utility Session save/load, export charts/data
    - Review: Save/load test, exported file QA
    4. LLM Prototype LLM chat for basic queries, report generation (OpenAI API or local)
    - Review: LLM responds to at least 3 user test queries, generates summary
    5. Geospatial Export KML/KMZ flight path export, Google Earth playback
    - Review: Visual flight path on Google Earth from test export
    6. Map/3D Viewer Optional: In-app map viewer with basic animation
    - Review: Trajectory visible in dashboard, responds to chart selection
    7. Advanced Utilities Derived parameters, annotations, automated checks
    - Review: User creates annotation, new parameter, sees automated data flag
