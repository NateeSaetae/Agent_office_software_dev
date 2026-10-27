# Natee’s Software House

Local AI Agent Office — React/TypeScript + React Three Fiber + FastAPI + SQLite + official Codex Python SDK.

## เปิดบนเครื่องนี้

1. ดับเบิลคลิก **Start Office.cmd** แล้วเปิด http://127.0.0.1:8010
2. ไปที่ **Settings → Check environment**
3. บัญชี ChatGPT ที่ Sign in แล้วจะอยู่ในพื้นที่ Credentials ของแอป ไม่ต้อง Sign in ซ้ำหลัง Restart
4. สร้าง Project → ใส่ Requirement → Ask Planner → อนุมัติแผน → Run workflow
5. แอปจะหยุดรอเมื่อมี Diff หรือ Test ที่ต้องอนุมัติ เปิดจากไอคอนกระดิ่งหรือแถบแจ้งเตือนด้านล่าง

ถ้าไม่ระบุ Workspace แอปจะสร้างโฟลเดอร์แยกให้โดยอัตโนมัติ หากระบุเอง ให้เลือกโฟลเดอร์เฉพาะโปรเจกต์ ไฟล์ Source ที่อยู่ในขอบเขตจะถูกส่งให้ Codex เมื่อคุณเริ่ม Run

## สถานะการตรวจสอบบนเครื่องนี้

- Frontend: TypeScript และ Production Build ผ่าน
- Backend: Contract/Security/Workflow Tests 22 กรณีผ่าน
- Browser: ฉาก WebGL และหน้า UI เปิดได้
- Authentication: ตรวจพบ ChatGPT Plus ผ่าน SDK จริง
- Full Codex run: ยังตรวจสอบไม่จบ เนื่องจาก Process ที่เรียกจากแชตนี้เข้า Windows Sandbox Provisioning Service ไม่ได้
- Docker: ปิดการใช้งานแล้ว ไม่ต้องติดตั้งหรือเปิด Docker Desktop

ห้ามตีความผล Unit/Contract Tests ว่าเป็นผลการรัน LLM หรือ Docker ครบวงจร ตัว FakeProvider ใช้เฉพาะในไฟล์ทดสอบ ไม่มี Demo Provider ในแอปจริง

## เตรียม Environment เมื่อ Check environment ไม่ผ่าน

เปิด **Start Office.cmd จาก Windows โดยตรง** เพื่อให้ Backend ทำงานนอก Sandbox ของแชตนี้ แล้วตรวจใหม่

สำหรับ Codex บน Windows แอปเลือก MXC เมื่อเครื่องรองรับ และใช้ elevated sandbox เป็น fallback หากยังไม่ได้ Provision ให้เปิด **Setup Sandbox.cmd** ด้วยตัวเอง ขั้นตอนนี้อาจมี UAC และสร้าง Sandbox Accounts/Firewall Configuration ของ Codex ตามกระบวนการทางการ แอปจะไม่ปิด Sandbox เพื่อเลี่ยงข้อผิดพลาด

DevOps ตรวจ Dependencies, Build Configuration และเตรียมคำสั่งรัน Local ได้โดยไม่ใช้ Docker ระบบไม่เรียก Container หรือรัน Source ของโปรเจกต์ผ่าน Host Shell อัตโนมัติ ส่วน QA ยังเสนอไฟล์ทดสอบได้ แต่การ Execute Tests ต้องตรวจด้วยตัวเองใน Project Workspace และจะแสดง Blocked รอหลักฐานแทนการรายงานว่าผ่าน

เอกสารทางการ:
- https://learn.chatgpt.com/docs/codex-sdk
- https://learn.chatgpt.com/docs/app-server
- https://learn.chatgpt.com/docs/windows/windows-sandbox
- https://learn.chatgpt.com/docs/permissions

## ติดตั้งใหม่จาก Source

ต้องมี Python 3.12+ และ Node.js 20.19+ ไม่ต้องใช้ Docker Desktop

    python -m venv .venv
    .venv\Scripts\python.exe -m pip install -r apps\api\requirements.txt
    cd apps\web
    npm ci
    npm run build
    cd ..\..
    .venv\Scripts\python.exe run.py

หรือหลังสร้าง Virtual Environment ใช้:

    .\start.ps1 -Install -Port 8010

Production UI ถูก Serve โดย FastAPI จาก apps/web/dist และใช้ Origin เดียวกับ API ไม่มีขั้นตอน Deploy ไปภายนอก

Development:

    # Terminal 1
    .venv\Scripts\python.exe run.py
    # Terminal 2
    cd apps\web
    npm run dev

Vite ใช้ Port 5173 และ Proxy ไป Backend Port 8000 ในโหมด Development ส่วน Start Office.cmd ใช้ 8010

## ตรวจสอบ

    .venv\Scripts\python.exe check.py
    cd apps\web
    npm run build
    npm run test:office

check.py จะตั้ง Dependency Paths สำหรับสภาพแวดล้อมที่สร้างในแชตนี้ให้อัตโนมัติ และสร้าง Test Workspaces แยกใน work/

## สิ่งที่ทำได้ในรุ่น 0.1

- สร้าง Project พร้อม Requirement และ Workspace
- Agent 6 บทบาท พร้อม Instructions แยก
- ใช้ Codex Python SDK จริงผ่าน ChatGPT Sign-in ไม่ต้องใช้ API Key
- Planner คืน Structured Tasks พร้อม Dependencies และ Acceptance Criteria
- Sequential Workflow, Manual Run/Retry/Cancel และจำนวน Retry สูงสุด 3 ครั้ง
- อ่าน Source Snapshot แบบจำกัดขนาด เสนอ File Replacements และแสดง Unified Diff
- ตรวจ Hash หลังอนุมัติก่อนเขียนไฟล์ ปฏิเสธ Path Traversal และ Links/Junctions
- DevOps ตรวจและเสนอ Local Build/Run Configuration โดยไม่ใช้ Docker
- QA เสนอ Tests และคำสั่งตรวจแบบ Manual; ปิด Automated Project Test Execution ชั่วคราว
- QA ไม่ผ่านหากไม่มี Test ถูก Execute จริง
- เก็บ Projects, Tasks, Runs, Approvals และ Events ลง SQLite ผ่าน SQLAlchemy
- WebSocket Replay หลัง Reconnect, Expire Approval และ Mark Interrupted หลัง Restart
- ฉาก 2.5D Pixel Art รายละเอียดสูงตาม Reference พร้อมตัวละคร 6 แบบที่เห็นใบหน้า ห้องประชุม Lounge, Coffee Bar, โต๊ะ 6 โซน และ Server Racks
- Idle Roaming แบบ A* พร้อมเฟรมเดิน 4 เฟรมต่อตัวละคร และกลับโต๊ะเมื่อมีงานจริง; มีปุ่ม Pause และรองรับ Reduced Motion
- หน้า Office / Projects / Tasks / Agents / Activity / Settings และ Agent Detail Drawer

## ขอบเขตของรุ่นแรก

นี่คือ MVP ที่นำไปพัฒนาต่อได้ ยังไม่ใช่งานครบทุก Phase ของสเปกต้นฉบับ

- ฉากใช้ Pixel Art Environment Plate รายละเอียดสูง และแยก Sprite Characters เป็นวัตถุใน React Three Fiber เพื่อให้เดินและเลือกได้จริง กล้องเป็นมุมคงที่ ลากดูฉากได้เมื่อหน้าต่างแคบ
- ยังไม่มี Sprite Sheet ครบ 9 Animation States หรือ Depth of Field
- Agent รับ Source Snapshot สูงสุด 100,000 ตัวอักษร และ Source Index สูงสุด 500 ไฟล์ ไม่ใช่ Terminal อิสระ
- Native Codex Tools ถูกปิดและมี PreToolUse Deny Hook; File Changes กับ Tests ทำผ่าน Application Runtime
- การทดสอบ Repository ที่ต้องติดตั้ง Package ต้องเพิ่ม Sandbox Images/Runner ที่ตรวจสอบแล้ว
- เมื่อ QA มีหลักฐาน Test Failure จริง ระบบสร้างงานแก้ให้ Developer และวน QA ได้สูงสุด 3 Attempts; หากเป็นปัญหา Environment หรือไม่มี Tests จะหยุดให้ตรวจ
- ยังไม่มี Parallel Execution, Ollama Implementation, Git Commit/Push, Deployment หรือ Database Migration Tooling
- Provider Interface เตรียมไว้สำหรับ Ollama โดยยังไม่แสดงว่ารองรับจริง
- Runtime ใช้ Codex SDK/Permission Profiles ที่ Pin ไว้ ต้องตรวจใหม่ก่อนอัปเกรด
- รัน Backend หนึ่ง Process เท่านั้น ห้ามใช้หลาย Uvicorn Workers เพราะ Queue/Lease อยู่ใน Process
- App-local Credentials ถูกเก็บโดย Codex ใน .data/codex-home ต้องปกป้องสิทธิ์ของโฟลเดอร์นี้ ไม่ส่งต่อหรือ Commit
- Secret Filename Exclusions เป็นมาตรการลดความเสี่ยง ไม่สามารถตรวจพบ Secrets ที่ฝังใน Source Code ทุกชนิดได้
- Google Fonts เป็นตัวเลือกด้านภาพ หาก Offline จะใช้ Font สำรองของเครื่อง

## โครงสร้าง

    apps/api/app/
      main.py             API, Session/Origin Checks, WebSocket
      store.py            SQLAlchemy/SQLite Persistence + Events
      orchestrator.py     DAG, Workflow, Approval, Runtime Execution
      provider.py         Official Codex SDK Adapter
      agents.py           Role Definitions
      security.py         Workspace Tools + Manual Test Policy
      deny_native_tools.py
    apps/api/tests/       Isolated Contract/Security Tests
    apps/web/src/
      App.tsx             Product UI
      Office.tsx          Scene Rendering
      office/navigation.ts
      store.ts            Shared Backend State
    run.py                Backend Launcher
    check.py              Test Launcher

ข้อมูลใช้งานอยู่ใน .data/ ส่วน work/ เป็นไฟล์ชั่วคราว ทั้งสองโฟลเดอร์ถูก Ignore และไม่รวมใน Source Archive


รายละเอียดงานภาพ Assets และ Prompt ที่ใช้สร้าง: [docs/office-art.md](docs/office-art.md)

## Project folders and deletion

On the Projects page, each card shows the full workspace path. **Open folder** opens File Explorer on the local server computer (Windows); **Copy path** copies the absolute path.

**Delete project** permanently removes the entire workspace folder, including all subfolders, and the project's tasks, runs and approvals. It requires the exact project name and a confirmation checkbox. Stop all active runs/workflows first. Protected directories, overlapping project folders and linked/junction paths are refused. If deletion fails, the project record remains so the problem can be resolved; the error reports that files may already have been partially removed.

After updating backend code, restart the local server with `Start Office.cmd`, then refresh the browser with Ctrl+F5. The ChatGPT sign-in and remaining projects are preserved.

## Workspace appearance

The Tasks, Agents, Projects, Activity and Settings tabs use a shared modern white/blue theme, readable typography, capsule controls and bounded text panels. Task and Activity searches filter the visible records. See [workspace design](docs/workspace-design.md).
