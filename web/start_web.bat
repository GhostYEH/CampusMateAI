@echo off
title CampusMate AI - Vue Web
cd /d "%~dp0"
if not exist "node_modules" call npm install
call npm run dev
