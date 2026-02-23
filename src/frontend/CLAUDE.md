# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with the frontend extension in this directory.

## Overview

This is the frontend extension for Surogate Agent. It provides a UI layer that communicates with the `surogate-agent` REST API.

## API contract

The backend API is documented in `../../docs/api.md`. The base URL is configurable (default: `http://localhost:8000`).

Key endpoints:
- `POST /chat` — SSE stream for agent responses
- `GET/POST/DELETE /skills` — skill management
- `GET/DELETE /sessions/{id}` — session management
- `GET /workspace/{skill}` — developer workspace browsing

## Development

> Setup instructions will be added as the project is bootstrapped.
