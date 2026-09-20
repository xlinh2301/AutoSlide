# 🤖 Multi-Agent Orchestration & Quality Standards (AGENTS.md)

> [!IMPORTANT]
> **QUY TẮC BẮT BUỘC (MANDATORY)**:
> 1. Trước khi thực hiện bất kỳ thao tác hay nhiệm vụ nào, **TẤT CẢ CÁC AGENT (bao gồm cả Orchestrator)** đều **PHẢI ĐỌC `AGENTS.md`** hoặc nạp context bootstrap qua `.ai/context/SDLC_CONTEXT.md` (lệnh `/sdlc-context` / `sdlc-context show`) để nắm rõ vai trò (Role), ranh giới trách nhiệm (Boundaries), quy chuẩn kiểm thử và các lệnh thao tác.
> 2. **INJECT PROMPT BẮT BUỘC (MANDATORY PROMPT INJECTION)**:
>    Cứ **MỖI LẦN** prompt cho bất kỳ agent nào (Orchestrator giao việc, sub-agent dispatch, chuyển tiếp task, handover), **BẮT BUỘC PHẢI CHÈN THÊM DÒNG SAU VÀO CUỐI PROMPT**:
>    `Reference the AGENTS.md document for complete guidelines`

---

## 1. Phân định Vai trò & Ranh giới Trách nhiệm (Agent Roles & Boundaries)

```
                       ┌─────────────────────────┐
                       │       ORCHESTRATOR      │
                       │  (Dispatch & Merge only) │
                       └───────────┬─────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         ▼                         ▼                         ▼
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  AGENT CODING    │      │  AGENT TESTING   │      │  AGENT VERIFY    │
│  (Isolated WT)   │      │  (Env & API QA)  │      │ (Parity & Vision)│
└──────────────────┘      └──────────────────┘      └──────────────────┘
```

### 1.1. Orchestrator (Điều phối viên)
- **Nhiệm vụ cốt lõi**:
  - **LÀM RÕ YÊU CẦU TRƯỚC KHI GIAO VIỆC (CLARIFYING QUESTIONS FIRST)**:
    - Trước khi bẻ nhỏ hoặc giao bất kỳ task nào cho sub-agent, Orchestrator **BẮT BUỘC PHẢI HỎI LẠI USER** về tất cả các điểm chưa rõ ràng (unclear/ambiguity).
    - Hỏi liên tục từng câu hỏi làm rõ cho đến khi task **đạt độ rõ ràng tối thiểu 95%** (`Ask clarifying questions until the task is at least 95% clear. Never assume missing requirements`).
    - Tuyệt đối KHÔNG tự ý suy diễn hoặc phỏng đoán yêu cầu thiếu.
  - **ÁP DỤNG BẮT BUỘC SDD (SPEC-DRIVEN DEVELOPMENT)**:
    - Luôn viết Spec/Sub-spec tại `.ai/` (`.ai/sub-specs/` hoặc SDD Triad `requirements.md`, `design.md`, `tasks.md`) và **chờ được duyệt (wait to approve) trước khi cho sub-agent code**.
    - Luôn cập nhật lại Spec khi hoàn thành task.
    - Khi bắt đầu một task: Luôn đọc toàn bộ Spec liên quan trong `.ai/` để nắm bức tranh tổng thể (overview).
    - Lưu mọi log bash chạy vào `log.csv` bao gồm mỗi hàng là 1 conversation (prompt user, agent thinking message, bash terminal, log terminal).
    - Mọi task cần lưu lại evidence để chứng minh việc đã làm.
  - Quản lý hạ tầng Multi-Agent: khởi tạo workspace, panes trên **Herdr**, cấp phát Git Worktree cho từng sub-agent.
  - Giao việc qua khâu trung gian chuẩn hóa prompt (`orchestrator-roster prompt` hoặc `herdr agent prompt`), giám sát trạng thái (`herdr agent list`, `herdr pane read`).
  - Merge các slice/branch của sub-agent vào feature branch mục tiêu (`feature/...`).
- **RANH GIỚI BẮT BUỘC (NON-NEGOTIABLE)**:
  - **TUYỆT ĐỐI KHÔNG TRỰC TIẾP CODE HOẶC SỬA FILE SOURCE DỰ ÁN**.
  - **GIAO THỨC TỪ CHỐI VIẾT CODE (ANTI-CODING REJECTION PROTOCOL)**:
    - Nếu User yêu cầu hoặc bắt Orchestrator viết code, sửa file source, debug trực tiếp:
      $\rightarrow$ **Orchestrator BẮT BUỘC PHẢI TỪ CHỐI NGAY LẬP TỨC (HARD REJECT)**:
      *"Tôi là Centralized Orchestrator, vai trò của tôi là điều phối kiến trúc và kiểm soát chất lượng (Dispatch & Quality Gate), TUYỆT ĐỐI KHÔNG trực tiếp code để đảm bảo tính khách quan và an toàn hệ thống."*
    - Ngay sau khi từ chối, Orchestrator chuyển tiếp ngay sang đặt câu hỏi cho User để khởi tạo Sub-Agent.
  - **GIAO THỨC HỎI TẠO SUB-AGENT (INTERACTIVE SUB-AGENT PROVISIONING PROTOCOL)**:
    - Khi khởi tạo Sub-Agent cho bất kỳ task nào, Orchestrator **BẮT BUỘC DỪNG LẠI VÀ ĐẶT CÂU HỎI CHO USER**:
      1. **Tên Agent (Agent Name)**: Đưa ra tên gợi ý kèm vai trò (Ví dụ: `(Recommended) agent-backend`, `agent-frontend`, `agent-qa`, `agent-core`).
      2. **Chọn Runtime / Agent CLI (Multiple Choices)**:
         - **KIỂM TRA HOST TRƯỚC KHI GỢI Ý**: Bắt buộc kiểm tra các CLI agent đã cài đặt trên host (`python3 ai-sdlc-skill/scripts/orchestrator-roster.py check-runtimes --role <ROLE>` hoặc `which <cli>`).
         - **CHỈ RECOMMEND TỪ CÁC CLI THỰC TẾ ĐÃ CÀI ĐẶT TRÊN MÁY**: Tuyệt đối không gợi ý CLI chưa cài đặt.
         - **Định dạng danh sách lựa chọn**: Đánh dấu rõ trạng thái `[ĐÃ CÀI ĐẶT - RECOMMENDED]` cho runtime tối ưu nhất có sẵn trên máy, `[ĐÃ CÀI ĐẶT]` cho các runtime khác có sẵn, và `[CHƯA CÀI ĐẶT]` cho các CLI còn lại.
    - Chỉ sau khi User xác nhận tên và Runtime, Orchestrator mới thực thi cấp phát Git Worktree (`worktree/<NAME>`) và mở pane Herdr (`herdr pane split && herdr agent start <NAME> --kind <CLI>`).
  - **TUYỆT ĐỐI KHÔNG TRỰC TIẾP TEST/CURL ĐỂ THỰC HIỆN CÔNG VIỆC CỦA QA**.
  - **TUYỆT ĐỐI KHÔNG DÙNG TOOL NATIVE SUB-AGENT (như invoke_subagent, Task tool, hoặc mở tab/trang mới của IDE)**. BẮT BUỘC 100% khởi tạo sub-agent trong Herdr PTY thông qua CLI: `orchestrator-roster launch` hoặc `herdr pane split && herdr agent start`.
  - Không tự ý merge vào các nhánh bảo vệ (`master`, `release-*`, `develop`).

### 1.2. Agent Coding (`agent-coding` / `agent-core`, `agent-parser`,...)
- **Nhiệm vụ**:
  - Đọc kỹ spec/sub-spec và code context trước khi viết mã.
  - Chỉ thao tác trong Git Worktree cô lập của riêng mình.
  - Tự chạy unit test / syntax check nội bộ trong worktree trước khi commit.
  - Commit mã nguồn tuân thủ nghiêm ngặt **Conventional Commits** (`feat:`, `fix:`, `refactor:`). Tuyệt đối không thêm `Co-Authored-By` hay AI attribution.
  - Tuân thủ quy chuẩn Code Hygiene:
    - Minimize unnecessary code changes.
    - Reuse existing code whenever possible.
    - Follow the project's coding style and structure.
    - Never overwrite or delete important files without explicit user confirmation.
  - **Nguyên tắc bất đồng bộ**: Khi hoàn thành slice của mình, lập tức commit và báo DONE để chuyển giao cho verify, không cần chờ các agent coding khác nếu không có dependency.

  - **Interactive MR Gate**: Sub-agent chỉ sinh báo cáo nghiệm thu và báo Orchestrator. Sau completion bắt buộc dừng ở `WAITING_USER_MR_APPROVAL`; tuyệt đối không tự tạo, push hoặc gửi GitLab MR. Chỉ approval rõ ràng của User mới cho phép chuyển sang `USER_MR_APPROVED`.

### 1.3. Agent Testing (`agent-testing` / `agent-qa`)
- **Nhiệm vụ**:
  - Quản lý môi trường thực thi (Docker containers, service startup, healthcheck).
  - Soạn thảo và chạy kịch bản kiểm thử API tự động (curl, pytest, postman collections).
  - Đo đạc metrics hiệu năng: latency (`response_time`), throughput, HTTP status codes (200, 400, 403, 500).

### 1.4. Agent Verify (`agent-verifier` / `agent-auditor`)
- **Nhiệm vụ**:
  - Đối soát **Data Parity** giữa mã mới và Baseline (so sánh từng trường dữ liệu semantic).
  - Chạy audit mã nguồn: `pre-commit run --all-files`, code hygiene, linting.
  - Chạy `pr-agent` review tự động trên diff trước khi merge.
  - **Vision Verification**:
    - Khi task liên quan đến hình ảnh, bounding boxes, OCR crops, alignment: **BẮT BUỘC** sử dụng bộ công cụ **`agent-vision-toolkit`** (https://github.com/Anionex/agent-vision-toolkit) đã được cài đặt sẵn tại `~/.local/bin/` (`crop`, `glance`, `detect`, `ground`, `trace`) để trực quan hóa, kiểm tra tọa độ bounding box, crop vùng nghi vấn và đối soát thị giác.

### 1.5. Quy tắc Inject Prompt Bắt buộc & Khâu Trung Gian (Mandatory Structured Prompt Injection)

> [!CAUTION]
> **QUY TẮC BẮT BUỘC CHO MỌI LẦN PROMPT SUB-AGENT**:
> Mọi task từ User trước khi chuyển giao cho sub-agent (`herdr agent prompt`, CLI dispatch, handover) **BẮT BUỘC PHẢI ĐƯỢC CHUẨN HÓA QUA KHÂU TRUNG GIAN** theo đúng cấu trúc chuẩn sau:
> 
> ```markdown
> ## Task
> - <TASK_DESCRIPTION>
> 
> ## Communication
> - Ask clarifying questions until the task is at least 95% clear.
> - Never assume missing requirements.
> - If any ambiguity arises during implementation, stop and ask for clarification.
> - Follow these rules unless the user explicitly overrides them.
> 
> ## Base Rules
> - Always follow AGENTS.md
> - Orchestrator not coding
> - Always write spec and wait to approve before coding @.ai
> - Always update spec when task is done.
> - When start a task, read all spec for overview if needed.
> - Hãy lưu mọi log bash chạy vào một file log.csv bao gồm mỗi hàng là 1 conversation, gồm prompt user, agent thinking message, bash terminal, log terminal
> - Mọi task cần lưu lại evidence để chứng minh việc đã làm
> 
> ## SDD & Sub-Spec Standards (BẮT BUỘC TUÂN THỦ)
> - Canonical Template: BẮT BUỘC đọc và tuân thủ 100% template .ai/templates/sdd-sub-spec.md. Tuyệt đối không tự ý chế template mới hoặc bỏ sót bất kỳ mục nào (đặc biệt là Frontmatter YAML đầy đủ và ## 6. Kết nối Tri thức (Intelligence Context)).
> - Vị trí & Quy ước đặt tên Sub-Spec:
>   * Sub-Spec là DUY NHẤT 1 file markdown đặt trực tiếp tại: .ai/sub-specs/SDD-SUB-<YYYYMMDD>-<INDEX>-<SLUG>-<AGENT_NAME>.md
>   * TUYỆT ĐỐI KHÔNG tạo thư mục con trong .ai/sub-specs/ và KHÔNG đặt bộ ba Triad (requirements.md, design.md, tasks.md) vào trong .ai/sub-specs/ (Triad CHỈ thuộc phạm vi .ai/specs/<FEATURE_ID>/).
> - Approval Gate: Sau khi tạo/sửa Sub-Spec, phải commit lên worktree và DỪNG LẠI chờ Orchestrator/User phê duyệt (status: APPROVED) trước khi bắt đầu viết bất kỳ dòng code logic nào.
> - Cập nhật Spec: Khi hoàn thành task, luôn cập nhật trạng thái và kết quả thực tế vào Sub-Spec.
> 
> ## Coding
> - Minimize unnecessary code changes.
> - Reuse existing code whenever possible.
> - Follow the project's coding style and structure.
> - Never overwrite or delete important files without explicit user confirmation.
> 
> Reference the AGENTS.md document for complete guidelines
> ```
> 
> **Lệnh Prompt & Dispatch Chuẩn**:
> ```bash
> # Cách 1: Tự động format và prompt thẳng vào agent qua orchestrator-roster (Mặc định tiếng Anh)
> python3 ai-sdlc-skill/scripts/orchestrator-roster.py prompt --agent <AGENT_NAME> --task "<TASK_DESCRIPTION>"
> 
> # Cách 2: Chọn tiếng Việt tường minh nếu cần (--lang vi)
> python3 ai-sdlc-skill/scripts/orchestrator-roster.py prompt --agent <AGENT_NAME> --task "<TASK_DESCRIPTION>" --lang vi
> 
> # Cách 3: Format prompt trung gian rồi truyền vào herdr CLI
> FORMATTED_PROMPT=$(python3 ai-sdlc-skill/scripts/orchestrator-roster.py format-prompt "<TASK_DESCRIPTION>")
> herdr agent prompt <AGENT_NAME> "$FORMATTED_PROMPT"
> ```
> Tuyệt đối không được gửi bất kỳ prompt nào tới agent mà thiếu cấu trúc chuẩn này.

### 1.5.1. Chính sách Ngôn ngữ Điều phối (Machine-to-Machine Language Policy)
- **MẶC ĐỊNH TIẾNG ANH (`en`) CHO PAYLOAD MÁY**:
  - Mọi dữ liệu trao đổi giữa các agent (machine-to-machine payloads: task briefs, structured prompts, handover blocks, checkpoint reports, acceptance criteria) **MẶC ĐỊNH DÙNG TIẾNG ANH (`en`)**.
  - **Lý do**: Ký tự tiếng Việt có dấu mã hóa multibyte UTF-8 tốn nhiều token BPE hơn (đo lường thực nghiệm: tiết kiệm 9.61% trên template prompt chuẩn: 541 -> 489 tokens và loại bỏ overhead multibyte). Sử dụng tiếng Anh giúp tiết kiệm token context window và giảm độ trễ inference.
- **CHỌN TIẾNG VIỆT TƯỜNG MINH KHI CẦN**:
  - Tiếng Việt (`vi`) vẫn được hỗ trợ 100% khi người dùng hoặc orchestrator truyền tường minh cờ `--lang vi` hoặc đặt `"language": "vi"` trong file cấu hình `.ai/roster.json`.
  - Cuộc trò chuyện giao tiếp với người dùng (User chat) vẫn có thể là tiếng Việt, trong khi các prompt trung gian và báo cáo máy giữa các agent giữ nguyên chuẩn tiếng Anh (`en`).

### 1.5.2. Tùy chọn Tối ưu Token & Backend Headroom (Opt-In Token Saver & Headroom Invariant)
- **OPT-IN CHẶT CHẼ - TẮT MẶC ĐỊNH (DISABLED BY DEFAULT)**:
  - Tầng tối ưu hóa token và tích hợp Headroom (`headroom-ai`, CLI `headroom`) là **TÙY CHỌN (OPTIONAL)** và **TẮT MẶC ĐỊNH**.
  - Chỉ kích hoạt khi người dùng yêu cầu tường minh (qua cờ `--token-saver` trên CLI hoặc `"token_saver": {"enabled": true}` trong `roster.json`).
  - **TUYỆT ĐỐI KHÔNG TỰ ĐỘNG BẬT (NEVER AUTO-ENABLE)**.
- **DEGRADE GRACEFULLY (PASS-THROUGH FALLBACK)**:
  - Nếu Headroom chưa cài đặt trong môi trường hoặc proxy (`http://127.0.0.1:8787`) không khả dụng, hệ thống tự động fallback sang pass-through (hoặc native compression), tuyệt đối không bao giờ làm gián đoạn hoặc gãy luồng thực thi của sub-agent.
  - Có thể đảo ngược tức thì (trivially reversible): chỉ cần bỏ cờ `--token-saver` hoặc set `enabled: false`.
  - **CẤM prompt compute node tự phát**: Không hỏi/route node từ xa khi chưa có opt-in tường minh (`--remote` hoặc `[compute-mode]`). Luồng local mặc định, `--auto` và non-interactive tuyệt đối không được block chờ chọn node; không có fallback ngầm local ➜ remote.
- **KIỂM SOÁT I/O KHÔNG MẤT DỮ LIỆU (LOSSLESS CRITICAL LINE PRESERVATION)**:
  - Khi rút gọn hoặc cắt tỉa logs, tool outputs, file dumps: **BẮT BUỘC** bảo toàn 100% byte-exact các dòng trọng yếu (`Error:`, `Exception:`, `Traceback`, `AssertionError`, `FATAL`, `FAIL`, unified git diffs `---`/`+++`/`@@`, pytest summary).
  - Giới hạn runaway outputs (ngắt log vô tận ở ngưỡng an toàn) kèm ghi chú minh bạch.

### 1.6. Quy chuẩn Bootstrap Init Dự Án & Mandatory Injection cho Orchestrator

#### 1.6.1. Prompt Mẫu Bootstrap Khởi tạo Dự án Lần đầu (One-Shot Bootstrap Init)
Khi mở một Agent mới tại thư mục gốc của một dự án cần áp dụng SDLC:
```markdown
Bạn là Centralized Orchestrator theo chuẩn SDLC Multi-Agent. Hãy khởi tạo toàn bộ hạ tầng điều phối cho dự án này:

1. Cài đặt bộ công cụ SDLC và Slash Commands:
   bash ai-sdlc-skill/install.sh --project .

2. Kiểm tra các điều kiện tiên quyết (Prerequisites):
   - Git: Repo sạch sẽ trên branch chính.
   - Herdr Daemon: Kiểm tra socket `~/.config/herdr/herdr.sock` qua `herdr workspace list`. Nếu daemon chưa chạy, khởi chạy `herdr daemon &`.
   - Python 3 & Docker: Xác thực sẵn sàng cho container fast mount và memory store.

3. Kích hoạt L0-L3 Shared Memory:
   - Khởi tạo `.ai/memory/` và nạp architectural policies tại `l3_system_persona.md`.

4. Thiết lập Cam kết Vai trò (Role Invariant):
   - Tự xác nhận vai trò: Orchestrator chỉ làm nhiệm vụ phân rã task và dispatch sub-agent vào Herdr PTY.
   - TUYỆT ĐỐI KHÔNG dùng tool native sub-agent (invoke_subagent / Task tool / mở trang mới). 100% sub-agent phải chạy qua Herdr CLI.
   - TUYỆT ĐỐI KHÔNG trực tiếp sửa code hoặc test curl trên project root.

Báo cáo trạng thái sẵn sàng của dự án sau khi hoàn tất.
Reference the AGENTS.md document for complete guidelines
```

#### 1.6.2. Mandatory Injection Cho Orchestrator (Bắt buộc trong MỌI lượt Prompt giao việc)
Khi người dùng giao việc cho Orchestrator, hoặc tự động inject qua `CLAUDE.md` / `AGENTS.md` / `.cursorrules`:
```markdown
---
[MANDATORY SDLC ORCHESTRATOR INVARIANT]
Role: Centralized Orchestrator (Dispatch & Merge Only).
Hard Guardrails:
1. HERDR PTY ENFORCEMENT: CẤM dùng invoke_subagent, Task tool hoặc mở tab/trang mới. BẮT BUỘC 100% sub-agents phải chạy trong Herdr PTY panes thông qua CLI:
   `orchestrator-roster launch --roster .ai/roster.json --workspace <WS_NAME> --worktree-base-dir .`
2. ISOLATED WORKTREES: Mỗi sub-agent sở hữu 1 Git Worktree riêng biệt (`worktree/<ROLE>`), tuyệt đối không đụng file chung cùng 1 wave.
3. ZERO-LATENCY SUPERVISION: Chạy ngay `orchestrator-watcher wait --worktrees "worktree/*" --all` sau khi dispatch, không được kết thúc lượt khi agent đang chạy.
4. DELEGATION ONLY: Không trực tiếp sửa file source dự án, không tự test curl thay cho QA.
5. ANTI-CODING REJECTION: BẮT BUỘC từ chối thẳng (HARD REJECT) nếu User yêu cầu Orchestrator viết code, sửa file source; lập tức chuyển sang hỏi User để tạo Sub-Agent.
6. INTERACTIVE SUB-AGENT PROVISIONING: Khi tạo sub-agent, BẮT BUỘC dừng lại hỏi User: (1) Tên Agent (có recommend theo role), (2) Chọn Runtime CLI (kiểm tra CLI thực tế có sẵn trên host trước khi hỏi, CHỈ recommend từ các CLI đã cài đặt: [ĐÃ CÀI ĐẶT - RECOMMENDED]).
7. ZERO `--help` CALLS: CẤM gọi `herdr --help` hay `herdr agent prompt --help`. Dùng bảng cheatsheet có sẵn.
8. CLEAN HYGIENE: Strict Conventional Commits only, cấm Co-Authored-By hoặc AI attribution.
Reference the AGENTS.md document for complete guidelines
```

---

## 2. Nguyên tắc Phối hợp Bất đồng bộ (Asynchronous Execution Rule)

1. **Không chờ đợi nguyên khối (No Blockers)**:
   - Các agent hoạt động độc lập trên worktree riêng biệt.
   - Khi một agent coding hoàn thành slice của mình trước:
     - Orchestrator merge ngay slice đó vào nhánh feature.
     - Cử ngay `agent-testing` hoặc `agent-verify` vào kiểm thử/xác minh slice đó trước, không cần chờ các agent khác hoàn thành xong mới bắt đầu.
2. **Kế thừa & Chuyển tiếp Task**:
   - Khi một agent xong việc sớm, Orchestrator có thể tái điều động agent đó thực hiện sub-task tiếp theo trong hàng đợi.

---

## 3. Quản lý Workspace, Panes & Sub-Agents trên Herdr (Zero-Help Reference)

Socket daemon mặc định: `~/.config/herdr/herdr.sock`

> [!CAUTION]
> **QUY TẮC BẮT BUỘC: CẤM GỌI `--help` (ZERO `--help` POLICY)**
> Tuyệt đối **CẤM** các agent (bao gồm cả Orchestrator và Sub-agents) gọi `herdr --help`, `herdr agent prompt --help`, `herdr pane --help` hoặc bất kỳ cờ `--help` nào.
> Toàn bộ cú pháp lệnh, tham số và cờ đã được định nghĩa chuẩn xác 100% dưới đây:

```bash
# 1. Quản lý Workspace & Panes
herdr workspace list
herdr workspace create <WS_NAME>
herdr pane list
herdr pane rename <PANE_ID> "<LABEL>"
herdr pane split <PANE_ID> --direction right --cwd <WORKING_DIRECTORY>
herdr pane split <PANE_ID> --direction down  --cwd <WORKING_DIRECTORY>
herdr pane read <PANE_ID> --lines 50
herdr pane send-text <PANE_ID> "<COMMAND>"
herdr pane send-keys <PANE_ID> enter

# 2. Khởi chạy & Điều phối Sub-Agent Runtime (Antigravity agy)
herdr agent start <AGENT_NAME> --kind agy --pane <PANE_ID> -- --dangerously-skip-permissions
herdr agent list
herdr agent read <AGENT_NAME> --lines 50
herdr agent rename <OLD_NAME> <NEW_NAME>

# 3. Gửi Prompt đến Sub-Agent (KHÔNG cần thêm cờ --wait vì SDLC dùng inotify watcher)
# Cách 1 (Khuyên dùng): Tự động inject prompt chuẩn qua orchestrator-roster
orchestrator-roster prompt --agent <AGENT_NAME> --task "<TASK_DESCRIPTION>"

# Cách 2: Truyền trực tiếp qua herdr CLI kèm injected prompt
herdr agent prompt <AGENT_NAME> "<INJECTED_PROMPT>"

# 4. Giám sát & Chờ hoàn tất (Dùng Linux inotify Kernel Events <50ms)
orchestrator-watcher wait --worktrees "worktree/*" "worktree-*" --all --timeout 300
# Hoặc Herdr wait native:
herdr agent wait <AGENT_NAME> --until idle --timeout 300000
```

---

## 4. Quy chuẩn Cô lập Git Worktree cho Sub-Agent

Mỗi agent coding/mutation **BẮT BUỘC** sở hữu 1 worktree riêng nằm gọn trong thư mục `worktree/`:

```bash
# 1. Tạo worktree riêng từ nhánh feature vào thư mục gom nhóm worktree/
git -C <REPO_PATH> worktree add -B agent/<AGENT_NAME> worktree/<AGENT_NAME> <BASE_FEATURE_BRANCH>

# 2. Sub-agent commit trên worktree (Strict Conventional Commits, NO Co-Authored-By)
git add . && git commit -m "feat(scope): <message>"

# 3. Orchestrator merge nhánh của sub-agent vào feature branch
git merge agent/<AGENT_NAME> --no-ff -m "merge: integrate sub-agent <AGENT_NAME> slice"

# 4. Dọn dẹp worktree sau khi hoàn tất
git worktree remove worktree/<AGENT_NAME> --force
git branch -D agent/<AGENT_NAME>
git worktree prune
```

---

## 5. Bộ Công cụ Đo kiểm, Sanitizer & Quality Gate

```bash
# 1. Git Pre-Commit & Pre-Push Sanitizer Gate (Chống rò rỉ secret / local machine paths)
sanitizer-engine pre-commit
sanitizer-engine pre-push
# Tự động redact /media/..., /home/... thành @/ hoặc $HOME trong file .md, .json, .yaml
# Hard-block chặn commit/push nếu phát hiện API key, private key, JWT, AWS token.
# Cho phép bypass test fixture giả định: thêm '# pragma: allowlist secret' vào cuối dòng.

# 2. Pre-commit hooks (Clean diff & code hygiene)
pre-commit run --all-files

# 3. PR-Agent (Automated diff review cục bộ qua stdin)
git diff <BASE_BRANCH>...HEAD -- <PATHS> | pr-agent --stdin review

# 4. Agent Vision Toolkit (Kiểm tra hình ảnh, OCR, Bounding Box)
crop <IMAGE_PATH> --box "<X1,Y1,X2,Y2>" --out cropped.png
glance <IMAGE_PATH>
trace <IMAGE_PATH> --boxes "[[...]]" --out overlay.png
```

---

## 6. BÀI HỌC VÀNG VỀ KIỂM ĐỊNH DATA PARITY (Quality Lessons)

> [!CAUTION]
> **KHÔNG BAO GIỜ CHỈ NHÌN VÀO HTTP 200 HOẶC LATENCY ĐỂ KẾT LUẬN THÀNH CÔNG!**

1. **Kiểm tra độ đầy đủ của Payload (Field Completeness)**:
   - Một response trả về nhanh nhưng các trường cốt lõi (`name`, `address`, `date_of_birth`, `no`, `status`) bị rỗng `""` là **THẤT BẠI HOÀN TOÀN**.
   - Bắt buộc phải so sánh từng trường dữ liệu semantic so với Baseline (container port 8080).

2. **Nguyên lý Fallback & Backward Compatibility**:
   - Thẻ thường (`FRONT` như `samples/v2/6.png`, `1.png`): Pipeline v2 **BẮT BUỘC** phải trích xuất đầy đủ các trường thông tin chuẩn như Baseline v1.
   - Thẻ định dạng mới: Áp dụng quy tắc trích xuất nâng cao v2.
   - Tuyệt đối không được nuốt dữ liệu hoặc drop về rỗng khi thẻ không khớp rule mới.

3. **Xác thực API Key**:
   ```bash
   API_KEY=$(awk '{print $3}' src/api/apikey/keys.txt)
   curl -s -X POST http://localhost:18098/jrc/v2/recognition \
     -H "Authorization: Bearer $API_KEY" \
     -F "image=@samples/v2/6.png" | jq .
   ```

---

## 7. BÀI HỌC VẬN HÀNH & KINH NGHIỆM MULTI-AGENT RUNTIME (Operational Lessons)

### 7.1. Quản lý Quota & Chuyển đổi Runtime Linh hoạt (Runtime Failover)
- **Vấn đề**: Các sub-agent chạy model thương mại (như OpenAI Codex `gpt-5.6-terra` / `luna`) dễ gặp lỗi `HTTP 429 Too Many Requests` khi tác vụ yêu cầu nhiều turns và xử lý đồng thời.
- **Giải pháp**:
  - Không cố gắng retry mù quáng làm cạn kiệt thời gian và context.
  - Thoát agent cũ về shell prompt (`/exit` hoặc gửi EOF) và lập tức chuyển đổi runtime sang **`agy` (Antigravity CLI)** với Gemini (ví dụ: `Gemini 3.8 Flash`) qua Herdr:
    ```bash
    herdr agent start <AGENT_NAME> --kind agy --pane <PANE_ID> -- --dangerously-skip-permissions
    herdr agent prompt <AGENT_NAME> "<TASK_PROMPT>. Reference the AGENTS.md document for complete guidelines"
    ```
  - `agy` vận hành ổn định, tốc độ inference cao, giải quyết triệt để nút thắt cổ chai API quota.

### 7.2. Chiến lược Môi trường Container: Tránh Build Trần từ Đầu (Fast Mount vs Bare Build)
- **Vấn đề**: Việc sub-agent chạy `docker build -f src/Dockerfile src` từ đầu sẽ kéo hàng loạt package hệ điều hành và thư viện nặng (`numpy`, `scipy`, `pandas`, `Levenshtein`), tốn >10 phút và dễ bị cancel/timeout.
- **Quy tắc bắt buộc**:
  - **TUYỆT ĐỐI KHÔNG** build lại image từ con số không khi hệ thống đã có sẵn base image (`jrc:0.9.9` hoặc ID `0e989c44eccb`).
  - **Ưu tiên 1**: Sử dụng bind mount source code vào base image có sẵn:
    ```bash
    docker run -d --name <CONTAINER_NAME> -p <PORT>:80 -v <WORKTREE_PATH>/src:/server <BASE_IMAGE> sh run.sh
    ```
  - **Ưu tiên 2**: Nếu cần tạo image riêng, chỉ viết Dockerfile kế thừa `FROM <BASE_IMAGE>` và `COPY` đúng các file thay đổi (`manage.py`, `controller.py`, các module mới). Thời gian khởi động giảm từ 10+ phút xuống còn **vài giây**.

### 7.3. Phân lập Môi trường: Host vs Container Runtime
- **Vấn đề**: Môi trường host cục bộ có thể thiếu thư viện C hoặc các module nhị phân Cython (`.so`), gây lỗi giả tạo khi chạy `python3 -m py_compile` hay unit tests trực tiếp trên host.
- **Quy tắc**:
  - Các dependency chuyên sâu (như `Levenshtein`, engine nhận diện OCR, model weights) luôn được đóng gói đầy đủ bên trong container runtime.
  - Phải kiểm tra và thực thi smoke test trong chính container (`docker run --rm <IMAGE> ...` hoặc `docker exec <CONTAINER> ...`) để phản ánh đúng hiện trạng production.

### 7.4. Giữ gìn Vệ sinh Git trong Worktree (Git Hygiene)
- **Vấn đề**: Sub-agent tạo các symlink tạm (như `ln -s ... samples`) hoặc file log/kết quả tạm (`qa-build-retry.txt`) có thể làm ô nhiễm git status của worktree.
- **Quy tắc**:
  - Sub-agent phải dọn dẹp các symlink và file trung gian tạm thời trước khi commit.
  - Orchestrator trước khi merge **BẮT BUỘC** kiểm tra `git status` và `git diff --stat` trên worktree của sub-agent để đảm bảo diff tinh gọn, chỉ chứa code và artifacts chính thức.

---

## 8. CƠ CHẾ STATEFUL SESSION CHECKPOINT & HANDOVER (Zero-Loss Failover)

> [!TIP]
> **Mục tiêu**: Loại bỏ hoàn toàn hiện tượng "mất trí nhớ ngữ cảnh" (Context Amnesia) khi sub-agent bị hết quota, dính HTTP 429 hoặc cần chuyển đổi runtime. Sub-agent mới được điều động vào phải có khả năng tiếp quản công việc **ngay lập tức trong 0 giây** mà không tốn token/turns thăm dò lại từ đầu.

### 8.1. File Checkpoint Chuẩn: `SESSION_STATE.json`
Mỗi Git Worktree bắt buộc duy trì tệp `SESSION_STATE.json` ngay tại thư mục gốc của worktree.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "agent": "agent-qa",
  "role": "testing",
  "worktree": "/path/to/worktree-agent-qa",
  "branch": "agent/clean-qa",
  "spec_file": ".ai/sub-specs/SDD-SUB-20260904-002-clean-room-benchmark-v2.md",
  "phase": "TESTING",
  "updated_at": "2026-09-04T16:00:00+07:00",
  "progress": {
    "completed_milestones": [
      "Mounted feature code into container jrc-api-sdlc-2808 on port 18098",
      "Verified baseline 8080 and feature 18098 responding 200 OK"
    ],
    "commits": ["ce5290b", "35fc5a5"],
    "current_blocker": null,
    "next_action": "Run python3 tests/qa_benchmark_v2.py --evidence qa-results-v2.json and record parity"
  },
  "runtime_metadata": {
    "containers": {
      "baseline": {"name": "jrc-api", "port": 8080},
      "feature": {"name": "jrc-api-sdlc-2808", "port": 18098, "base_image": "0e989c44eccb"}
    },
    "test_command": "python3 tests/qa_benchmark_v2.py --evidence qa-results-v2.json",
    "api_key_source": "src/api/apikey/keys.txt"
  }
}
```

### 8.2. Quy tắc Ghi Checkpoint (Save Triggers)
Sub-agent **BẮT BUỘC** cập nhật `SESSION_STATE.json` sau mỗi sự kiện sau:
1. **Khởi tạo môi trường thành công**: Đã mount/khởi động xong Docker container hoặc cài đặt xong test environment.
2. **Commit mã nguồn**: Vừa commit một slice (ghi lại commit hash và files).
3. **Gặp Blocker / Lỗi**: Khi gặp lỗi ngoại cảnh (429 rate limit, build failure, thiếu thư viện) -> Ghi ngay mô tả lỗi và bước cần khắc phục vào `current_blocker`.
4. **Trước khi kết thúc lượt (Turn Settled)**: Luôn cập nhật `next_action` là bước kế tiếp cần làm.

### 8.3. Quy trình Bàn giao Liền mạch (Handover Protocol khi Đổi Runtime)
Khi sub-agent bị treo, đứt kết nối hoặc dính HTTP 429:

```
┌────────────────────────┐         ┌────────────────────────┐
│  Agent cũ (Bị Rate 429)│         │  Orchestrator          │
└───────────┬────────────┘         └───────────┬────────────┘
            │                                  │
            │── 1. SESSION_STATE.json đã lưu ──▶│ (Phase, Blocker, Next Action)
            │   (hoặc Orchestrator đọc snapshot)│
            ▼                                  │
      [Thoát /exit]                            │── 2. Chuyển runtime sang agy
                                               │      herdr agent start ... --kind agy
                                               ▼
                                   ┌────────────────────────┐
                                   │  Agent mới (Kế thừa)   │
                                   └───────────┬────────────┘
                                               │
            ◀── 3. "Đọc SESSION_STATE.json ────│
            │       thực thi next_action ngay" │
            ▼                                  ▼
```

**Mẫu Prompt Handover chuẩn**:
```bash
herdr agent prompt <NEW_AGENT_NAME> "Read SESSION_STATE.json at the root of your worktree before acting.
The previous agent was interrupted due to rate-limit/failover.
Do NOT re-explore the codebase from scratch.
Resume immediately from phase: {phase} with next_action: {next_action}.
Reference the AGENTS.md document for complete guidelines"
```

---

## 9. Giao thức Giám sát Phản ứng & Báo xong Chuyên biệt (Event-Driven Agent Supervision Protocol)

Nhằm loại bỏ hiện tượng "mất dấu" (Signal Loss) và tránh việc Orchestrator phải liên tục polling hoặc đọc màn hình console rải rác text của LLM, hệ thống chuẩn hóa giao thức **Event-Driven Supervision** lấy cảm hứng từ kiến trúc `EventStream` của **OpenHands** và `Tool-level Termination` của **SWE-agent**:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR EVENT WATCHER                      │
│     (Lắng nghe Linux inotify kernel event trên worktree-*/.agent-event)│
└───────────────────────────────────▲────────────────────────────────────┘
                                    │
               Sự kiện tức thì (<50ms): .agent-event.json
                                    │
       ┌────────────────────────────┴────────────────────────────┐
       │                                                         │
┌──────────────┴──────────────┐           ┌──────────────┴──────────────┐
│  WORKTREE 1 (.agent-event)  │           │  WORKTREE 2 (.agent-event)  │
│  "event": "AGENT_FINISH"    │           │  "event": "HEARTBEAT"       │
│  "commit": "89805b2"        │           │  "phase": "UNIT_TESTING"    │
│  "tests_passed": 11         │           │  "status": "RUNNING"        │
└─────────────────────────────┘           └─────────────────────────────┘
```

### 9.1. Phía Sub-Agent: Phát tín hiệu với `agent-signal`
Mỗi sub-agent sau khi hoàn thành công việc hoặc trong quá trình thực thi bắt buộc sử dụng CLI `agent-signal` (đã có sẵn trong `$PATH`):

```bash
# 1. Báo cáo nhịp tim định kỳ khi đang thực thi
agent-signal heartbeat --phase "UNIT_TESTING"

# 2. Báo cáo HOÀN THÀNH khi đã commit mã nguồn và pass test
agent-signal finish --tests 12 --status "READY_FOR_QA"

# 3. Báo cáo THẤT BẠI khi gặp blocker / exception
agent-signal fail --reason "BuildError: missing dependency Levenshtein"
```

### 9.2. Phía Orchestrator: Giám sát phản ứng với `orchestrator-watcher`
Orchestrator không cần polling lặp lệnh thủ công. Sử dụng công cụ `orchestrator-watcher` (tích hợp Linux `inotify` + Watchdog Timeout):

```bash
# 1. Kiểm tra nhanh trạng thái tất cả sub-agent đang hoạt động
orchestrator-watcher status --worktrees "worktree-*"

# 2. Chờ phản ứng (Zero Latency) khi có BẤT KỲ sub-agent nào xong việc
orchestrator-watcher wait --worktrees "worktree-*" --timeout 180

# 3. Chờ cho đến khi TẤT CẢ các sub-agent trong Wave hoàn thành
orchestrator-watcher wait --worktrees "worktree-*" --timeout 300 --all
```

### 9.3. Ba Lớp Bảo vệ Tính Xác thực (Triple Verification Guard)
Khi `orchestrator-watcher` phát hiện event `AGENT_FINISH`:
1. **Kiểm tra chữ ký Git**: Tự động so khớp trường `commit` trong event với `git rev-parse HEAD` trên worktree tương ứng. Nếu commit không tồn tại trên HEAD ➔ Từ chối tín hiệu giả mạo.
2. **Watchdog Timeout**: Nếu một agent vượt quá ngưỡng timeout (ví dụ: 180s) mà không phát tín hiệu `AGENT_FINISH` ➔ Watchdog tự động trả về mã lỗi `TIMEOUT`, liệt kê danh sách các agent bị treo (`pending_agents`) để Orchestrator kịp thời kích hoạt Failover sang `agy`.
3. **Chuyển tiếp Tức thì sang QA**: Ngay khi nhận tín hiệu hợp lệ, Orchestrator lập tức cử `agent-qa` và `agent-verifier` vào nghiệm thu slice mà không có độ trễ.

### 9.4. Watcher Trung gian Chạy ngầm theo Project (`orchestrator-daemon`)

Nhằm khắc phục tình trạng Orchestrator (LLM) bị "ảo" hoặc kết thúc turn mà quên bật `orchestrator-watcher wait`, hệ thống cung cấp **Background Watcher Daemon trung gian**:

```bash
# 1. Khởi chạy Watcher Daemon chạy ngầm cho dự án hiện tại (tự động ghi PID vào .ai/daemon.pid)
orchestrator-daemon start --orchestrator-agent <ORCHESTRATOR_NAME>

# 2. Kiểm tra trạng thái Daemon của dự án (cô lập hoàn toàn giữa các project)
orchestrator-daemon status

# 3. Dừng Daemon khi kết thúc phiên làm việc
orchestrator-daemon stop
```

**Cơ chế Bơm Signal Đánh thức Chủ động (Active Wake-Up)**:
- Daemon chạy ngầm vĩnh viễn, lắng nghe inotify và quét liveness của các worktree thuộc project.
- Khi sub-agent `AGENT_FINISH`, `AGENT_FAILED`, hoặc `SILENT_DEATH`, Daemon **tự động gọi `herdr agent prompt <ORCHESTRATOR>`** để đánh thức Orchestrator ngay lập tức trong PTY!
- **Project Isolation**: Mỗi project quản lý daemon riêng qua `.ai/daemon.pid` và chỉ giám sát các worktree thuộc git repository của project đó. Nhiều project trên cùng máy chạy độc lập tuyệt đối, không xung đột.

---

## 10. TIÊU CHUẨN ĐIỀU PHỐI ORCHESTRATOR & LẬP LỊCH DAG (ORCHESTRATOR_SOP)

> [!IMPORTANT]
> Toàn bộ quy trình chuẩn về **Task Decomposition (Phân rã tác vụ theo Bounded Context)** và **Observability (Giám sát trạng thái phi hội thoại)** được quy định chi tiết tại:
> 👉 [**`ORCHESTRATOR_SOP.md`**](./ORCHESTRATOR_SOP.md)

### 10.1. Nguyên tắc Phân rã Tác vụ (Task Decomposition Matrix)
- **Cắt lát Dọc (Vertical Slicing)**: Mỗi sub-agent nhận trọn vẹn 1 slice độc lập bao gồm Logic + Unit Test + Schema.
- **Ranh giới Bounded Context**: Tuyệt đối không để 2 sub-agent cùng wave sửa chung 1 file code nhằm tránh merge conflict.
- **Quy tắc 300-400 LoC**: Sub-task vượt quá 400 dòng mã ước tính bắt buộc phải phân rã tiếp thành các sub-specs nhỏ hơn.

### 10.2. Công cụ Lập lịch Wave tự động: `orchestrator-dag`
CLI `orchestrator-dag` (đã có sẵn trong `$PATH`) sử dụng thuật toán Kahn để phân chia các task thành các Wave thực thi song song độc lập:

```bash
# 1. Tính toán kế hoạch Wave từ tasks.json (định dạng bảng hoặc json)
orchestrator-dag plan --spec .ai/specs/tasks.json --format table

# 2. Xuất kế hoạch Wave định dạng JSON cho kịch bản tự động hóa
orchestrator-dag plan --spec .ai/specs/tasks.json --format json
```

---

## 11. TIÊU CHUẨN THIẾT KẾ VAI TRÒ CỐ ĐỊNH & CHỐNG TRÔI DẠT VAI TRÒ (FIXED ROLES & ANTI-ROLE-DRIFT)

> [!IMPORTANT]
> **ĐỊNH ĐỀ BẢO TOÀN VAI TRÒ (ROLE CONSERVATION INVARIANT)**:
> Mỗi sub-agent khi được khởi tạo sở hữu một **Danh xưng & Ranh giới Cố định (Fixed Persona & Bounded Context)**.
> Tuyệt đối không để LLM tự do co giãn hoặc hoán đổi vai trò giữa chừng (Role Drift).

### 11.1. Ma trận 4 Vai trò Cố định Chuẩn (Canonical 4-Role Matrix)

| Vai trò Cố định | Nhiệm vụ Bắt buộc | Ranh giới Cấm đoán (Hard Guardrails) | Bộ Công cụ Được Cấp Phép |
| :--- | :--- | :--- | :--- |
| **`orchestrator`** *(Team Lead)* | • Phân tích PRD, sinh Spec Triad & Interface Contracts.<br>• Phân rã DAG Task, cấp phát Worktree.<br>• Giám sát Watchdog & Atomic Merge `--no-ff`. | • **Strict Delegation-First**: TUYỆT ĐỐI CẤM TRỰC TIẾP SỬA CODE DỰ ÁN khi có thành viên.<br>• Cấm tự test curl thay QA.<br>• Cấm merge khi thiếu chữ ký QA/Verify. | `orchestrator-dag`, `orchestrator-watcher`, `herdr workspace/pane`, `git merge` |
| **`agent-coding`** *(Worker / Implementer)* | • Đọc Sub-Spec và Interface Contract.<br>• Viết mã nguồn và unit test nội bộ trong worktree.<br>• Chạy test pass, commit Conventional Commit.<br>• Báo xong qua `agent-signal`. | • Chỉ sửa file trong Bounded Context của mình.<br>• Cấm sửa code của worktree khác.<br>• Cấm tự duyệt code của mình.<br>• Cấm chat lan man ngoài task. | `write_to_file`, `replace_file_content`, `run_command` (pytest local), `agent-signal` |
| **`agent-testing`** *(QA / Environment)* | • Dựng môi trường (Docker Fast Mount, Service).<br>• Chạy kịch bản kiểm thử API & E2E Integration.<br>• Đo đạc latency, throughput, HTTP status codes. | • **CẤM SỬA FILE LOGIC NGHIỆP VỤ** (nếu bug thì báo fail, không tự vá).<br>• Cấm bỏ qua lỗi assertion. | `docker`, `curl`, `pytest e2e`, `agent-signal` |
| **`agent-verifier`** *(Auditor / Reviewer)* | • Thẩm định Data Parity (Field Completeness).<br>• Kiểm tra code hygiene: linting, syntax, git diff.<br>• Xuất báo cáo nghiệm thu ký duyệt. | • **CẤM DUYỆT TỰ ĐỘNG BẰNG TEXT** (Bắt buộc so khớp SHA và test logs).<br>• Cấm merge nhánh. | `git diff`, `pre-commit`, `agent-vision-toolkit`, `agent-signal` |

### 11.2. Ba Cơ chế Cốt lõi Chống Trôi dạt Vai trò (Anti-Role-Drift Mechanisms)

1. **Roster Living Spec Invariant trong System Prompt**:
   Khi prompt hoặc spawn bất kỳ sub-agent nào, cấu trúc prompt bắt buộc mang định danh bất biến:
   ```text
   YOU ARE: {AGENT_NAME}
   FIXED ROLE: {ROLE_NAME} (Worker | QA | Auditor | Orchestrator)
   WORKSPACE WORKTREE: {WORKTREE_PATH}
   BOUNDED CONTEXT: {ALLOWED_DIRECTORIES}

   STRICT INVARIANTS:
   1. You only have authority over your BOUNDED CONTEXT. Touching other paths is a protocol violation.
   2. NEVER assume the duties of other teammates. If a dependency is missing, emit agent-signal fail/blocker.
   3. Zero-Ack Silence: Do not produce conversational pleasantries (e.g., "Understood", "I will do this"). Take immediate tool action or wait silently.
   Reference the AGENTS.md document for complete guidelines.
   ```

2. **Chế độ Hành động theo Lượt (Action Mode Enforcement)**:
   - **Chế độ `DO`**: Áp dụng khi agent nhận việc. Chỉ được gọi tool đọc, viết code, chạy test. Câu trả lời text thuần túy không kèm tool call bị coi là stall.
   - **Chế độ `DELEGATE`**: Khi hoàn tất slice, agent chỉ được gọi `agent-signal finish` và cập nhật `SESSION_STATE.json`. Cấm tự ý nhận thêm task khác nếu chưa có chỉ thị từ Orchestrator.

3. **Chân lý Giao vận: "Accepted != Responded" (Response Proof Ledger)**:
   - Việc gửi prompt thành công không đồng nghĩa với agent đã làm xong.
   - Trạng thái hoàn thành chỉ được Orchestrator công nhận khi có **Bằng chứng Phản hồi Thực chất (Response Proof)**:
     - Có tool call tạo tác động thực (`write_to_file`, `git commit`).
     - Commit SHA khớp tuyệt đối với `git rev-parse HEAD`.
     - Tín hiệu sự kiện nguyên tử `.agent-event.json` được phát ra.
   - Mọi câu chat dạng "Task completed successfully", "I'm done" mà thiếu commit SHA thật đều bị Watchdog từ chối.

---

## 12. CƠ CHẾ ĐIỀU PHỐI ĐA NỀN TẢNG & ROSTER ĐỘC LẬP RUNTIME (RUNTIME-AGNOSTIC MULTI-AGENT ROSTER)

> [!IMPORTANT]
> **ĐỊNH ĐỀ ĐỘC LẬP NỀN TẢNG (RUNTIME-AGNOSTIC PRINCIPLE)**:
> Hệ thống được thiết kế mở hoàn toàn, **KHÔNG GIỚI HẠN VÀO BẤT KỲ AGENT CLI CỤ THỂ NÀO**.
> Bất kỳ Agent CLI nào có mặt trong `$PATH` hoặc được hỗ trợ bởi Herdr (hơn 21+ loại: `claude`, `codex`, `agy`, `opencode`, `copilot`, `hermes`, `gemini`, `cline`, `devin`, `cursor`, `grok`, `kimi`, `kiro`,...) đều có thể được chỉ định làm runtime cho bất kỳ vai trò nào.
> Các ví dụ về `codex`, `agy`, `copilot` trong tài liệu chỉ mang tính chất minh họa thực nghiệm.

### 12.1. Ma trận Tương thích Khuyến nghị (Runtime Affinity Matrix)

| Vai trò Nghiệp vụ | Điểm mạnh Yêu cầu | Runtime Khuyến nghị (Ưu tiên) | Model Tiêu biểu |
| :--- | :--- | :--- | :--- |
| **`orchestrator` / `architect`** | Lập luận thiết kế sâu, tổng hợp hệ thống | `claude`, `codex`, `agy` | Claude 3.7 Sonnet, GPT-5, Gemini Pro |
| **`agent-backend` (Worker)** | Thuật toán, cấu trúc dữ liệu, REST API | `codex`, `claude`, `agy` | GPT-5.6 Luna / Terra, Claude Sonnet |
| **`agent-frontend` (Worker)** | UI/UX, DOM manipulation, responsive CSS | `agy`, `claude`, `copilot` | Gemini 3.8 Flash, Claude Sonnet |
| **`agent-qa` / `agent-supervisor`** | Tốc độ nhanh, deterministic, ít hallucinate | `copilot`, `agy`, `hermes`, `gemini` | MAI Code Flash, Gemini Flash |

### 12.2. Quy trình Pre-flight Roster Gate (Tự động Detect & Hỏi User)

Trước khi khởi chạy bất kỳ wave hoặc team nào, Orchestrator kích hoạt công cụ `orchestrator-roster`:

```bash
# 1. Quét nhanh toàn bộ Agent CLIs đã cài đặt trên host
orchestrator-roster detect

# 2. Phân bổ vai trò tương tác (Interactive Gate) hoặc tự động (Auto Mode)
orchestrator-roster plan --roles backend frontend qa --output .ai/roster.json

# 3. Khởi tạo workspace và dispatch từng agent với runtime tương ứng trên Herdr
orchestrator-roster launch --roster .ai/roster.json --workspace sdlc-multi-runtime
```

### 12.3. Roster Configuration Schema (`.ai/roster.json`)
```json
{
  "version": "1.0.0",
  "available_runtimes": {
    "codex": "codex",
    "agy": "agy",
    "copilot": "copilot"
  },
  "assignments": {
    "backend": "codex",
    "frontend": "agy",
    "qa": "copilot"
  }
}
```
Mỗi sub-agent trong Herdr sẽ được khởi chạy chính xác theo `--kind` đã duyệt:
- `herdr agent start agent-backend --kind codex --pane wD:p1`
- `herdr agent start agent-frontend --kind agy --pane wD:p2 -- --dangerously-skip-permissions`
- `herdr agent start agent-qa --kind copilot --pane wD:p3`




---

## 13. HỘI ĐỒNG THẨM ĐỊNH 3 AGENT & TIÊU CHUẨN CODE REVIEW 5 TRỤC (THE TRIAD REVIEW COUNCIL)

> [!IMPORTANT]
> **TIÊU CHUẨN THẨM ĐỊNH MÃ NGUỒN NGHIÊM NGẶT (5-AXIS CODE REVIEW)**:
> Dựa trên chuẩn mực công nghiệp của **Addy Osmani** (*Correctness, Readability, Architecture, Security, Performance*).
> Nhằm triệt tiêu điểm mù (blind spots) và tránh Context Bloat, toàn bộ mã nguồn trước khi merge vào nhánh chính **BẮT BUỘC** phải trải qua thẩm định độc lập từ **Hội đồng 3 Agent Chuyên biệt**.

### 13.1. Ba Vai trò Thẩm định Trực giao (The 3 Review Perspectives)

| Tác tử Thẩm định | Trục Thẩm định (Axes) | Trọng tâm Kiểm tra Bắt buộc | Runtime Khuyến nghị |
| :--- | :--- | :--- | :--- |
| **`agent-review-logic`** | **Axis 1 (Correctness)**<br>**Axis 3 (Architecture)** | • Đối chiếu từng dòng mã với **Sub-Spec / Requirements** gốc.<br>• Kiểm tra xử lý biên (null, empty, boundary) và error paths.<br>• Kiểm tra mùi thiết kế: Refactor có thực sự giảm độ phức tạp hay chỉ dời chỗ (*relocating complexity*)?<br>• Ngăn ngừa rò rỉ logic nghiệp vụ vào module dùng chung. | `codex`, `claude`, `agy` |
| **`agent-review-security`** | **Axis 4 (Security)**<br>**Axis 5 (Performance)** | • Xác thực & làm sạch input tại ranh giới hệ thống (sanitization).<br>• Ngăn chặn rò rỉ secrets, SQL/command injection, Auth bypass.<br>• Phát hiện truy vấn N+1, vòng lặp không giới hạn, blocking I/O trên hot-path.<br>• Dependency Discipline: Kiểm duyệt rủi ro thư viện mới. | `copilot`, `claude`, `hermes` |
| **`agent-review-quality`** *(Lead Judge)* | **Axis 2 (Readability & Simplicity)**<br>**Review Tests First!** | • **Review the Tests First**: Kiểm tra test có đo lường hành vi (*behavior*) thay vì chi tiết cài đặt (*implementation*).<br>• Simplicity: "1000 lines where 100 suffice?"<br>• Dead Code Hygiene: Loại bỏ code mồ côi, biến thừa `_unused`.<br>• **Tổng hợp phán quyết**: Gán nhãn và xuất bản `APPROVE` / `REQUEST_CHANGES`. | `agy`, `claude`, `gemini` |

### 13.2. Tiêu chuẩn Kích thước Diff (Change Sizing Budget)
- **~100 lines changed**: Xuất sắc (`EXCELLENT`) — Dễ review trong một lượt, độ rủi ro thấp.
- **~300 lines changed**: Chấp nhận được (`ACCEPTABLE`) — Cho một thay đổi logic đơn lẻ hoàn chỉnh.
- **>400 lines changed**: Vượt ngưỡng (`OVERSIZED`) — **BẮT BUỘC PHÂN RÃ** thành các slice dọc nhỏ hơn, trừ trường hợp có ngoại lệ được Tech Lead duyệt trước.

### 13.3. Quy chuẩn Nhãn Mức độ Nghiêm trọng (Severity Prefixes)

Mọi nhận xét của Hội đồng Review bắt buộc phải gắn tiền tố định danh theo Addy Osmani:

1. **`Critical:`** (Chặn Merge Tuyệt đối - 🔴 Blocks Merge): Lỗ hổng bảo mật nghiêm trọng, nguy cơ mất dữ liệu, hoặc sai lệch spec logic.
2. **Không tiền tố** (Bắt buộc sửa - 🟠 Required Change): Lỗi kiến trúc, thiếu test case quan trọng, hoặc vi phạm convention dự án.
3. **`Nit:`** (Tùy chọn - 🟡 Author Discretion): Góp ý nhỏ về format, đặt tên biến, comment.
4. **`Optional:` / `Consider:`** (Đề xuất Kiến trúc - 🔵 Architectural Suggestion): Hướng đi thay thế đáng cân nhắc.
5. **`FYI:`** (Thông tin tham khảo - ⚪ Informational).

### 13.4. Công cụ Điều phối Thẩm định: `orchestrator-review`

```bash
# 1. Kiểm tra kích thước diff trước khi review
orchestrator-review check-sizing --base main

# 2. Sinh prompt chuẩn chỉ cho từng vai trò trong hội đồng (kèm inject AGENTS.md)
orchestrator-review prompt --role logic --spec .ai/sub-specs/SDD-SUB-001.md
orchestrator-review prompt --role security
orchestrator-review prompt --role quality

# 3. Tổng hợp nhận xét và ra Phán quyết (Verdict)
orchestrator-review synthesize \
  --logic-file .ai/reviews/logic.md \
  --security-file .ai/reviews/security.md \
  --quality-file .ai/reviews/quality.md \
  --output .ai/reviews/FINAL_REVIEW.md
```

---

## 14. CƠ CHẾ BỘ NHỚ PHÂN TẦNG DÙNG CHUNG (TENCENTDB AGENT MEMORY — L0 TO L3 & SYMBOLIC CANVAS)

> [!IMPORTANT]
> **TRIẾT LÝ BỘ NHỚ DÙNG CHUNG (SHARED AGENT MEMORY)**:
> Kế thừa từ kiến trúc đột phá của **TencentDB-Agent-Memory**:
> - **Chống Flat Vector Search**: Từ chối việc cắt vụn dữ liệu rồi tìm kiếm mù mờ (blind search) trong vector store phẳng.
> - **Tiết kiệm tới ~60% Tokens**: Thay vì nhồi nhét hàng nghìn dòng log terminal thô vào prompt, hệ thống nén lịch sử thực thi thành **Mermaid Symbolic Canvas** và chỉ dùng `node_id` để drill-down khi thực sự cần thiết.

```
                  ┌──────────────────────────────────────────────┐
                  │ L3: System Persona & Architecture Policies   │ (Markdown File)
                  └──────────────────────┬───────────────────────┘
                                         ▼
                  ┌──────────────────────────────────────────────┐
                  │ L2: Scenarios & SOP Lessons (Past Bug Fixes) │ (l2_scenarios.json)
                  └──────────────────────┬───────────────────────┘
                                         ▼
                  ┌──────────────────────────────────────────────┐
                  │ L1: Shared Atoms (Ports, Keys, Endpoints)    │ (l1_atoms.json)
                  └──────────────────────┬───────────────────────┘
                                         ▼
                  ┌──────────────────────────────────────────────┐
                  │ L0: Offloaded Raw Traces & Verbose Tool Logs │ (l0_traces/*.log)
                  └──────────────────────────────────────────────┘
                                         ▲
                         (Tra cứu tức thì qua node_id)
```

### 14.1. Bốn Tầng Ngữ Nghĩa (The 4 Memory Layers)

| Tầng | Định danh | Vị trí Lưu trữ | Mục đích & Trách nhiệm |
| :--- | :--- | :--- | :--- |
| **`L0`** | **Traces (Log Thô)** | `.ai/memory/l0_traces/<node_id>.log` | Chứa output dài hàng ngàn dòng (pytest log, docker build trace, curl dump). Được offload ra ngoài context để chống phình token. |
| **`L1`** | **Atoms (Sự thật Nguyên tử)** | `.ai/memory/l1_atoms.json` | Các biến cấu hình dùng chung giữa các sub-agent (port baseline 8080, port feature 18098, api key, SHA nhánh). |
| **`L2`** | **Scenarios (Bài học & SOP)** | `.ai/memory/l2_scenarios.json` | Mẫu giải quyết sự cố đã đúc kết (Ví dụ: *"Docker bare build tốn 10p ➔ Dùng Fast Mount base image 0e989c44eccb"*). |
| **`L3`** | **Persona & System Policies** | `.ai/memory/l3_system_persona.md` | Các nguyên lý kiến trúc bất biến (Clean Architecture, Conventional Commits, No AI Attribution, 400 LoC Limit). |

### 14.2. Biểu tượng hóa Trạng thái bằng Mermaid Canvas (Symbolic Short-Term Memory)

Mỗi khi Orchestrator dispatch prompt cho các sub-agents, thay vì paste lại toàn bộ lịch sử trò chuyện, hệ thống sử dụng `orchestrator-memory inject-context` để sinh ra một Mermaid Canvas cực kỳ tinh gọn:

```mermaid
graph TD
    subgraph L3["L3 Policy: Clean Arch & No Attribution"]
        POL["Strict Conventional Commits & 5-Axis Gate"]
    end
    subgraph L1["L1 Shared Atoms"]
        ATM_baseline_port["baseline_port: 8080"]
        ATM_feature_port["feature_port: 18098"]
    end
    subgraph L0["L0 Offloaded Traces (Drill-Down via node_id)"]
        LOG-QA-01["[LOG-QA-01] API Parity verification passed 100%"]
    end
    POL -.-> L1
    L1 -.-> L0
```

Khi một agent gặp lỗi hoặc nghi vấn về kết quả kiểm thử, nó chỉ cần tra cứu theo `node_id`:
```bash
orchestrator-memory read-trace --node-id LOG-QA-01
```

### 14.3. Lệnh Thao tác Bộ nhớ Chuẩn: `orchestrator-memory`

```bash
# 1. Khởi tạo kho bộ nhớ dùng chung
orchestrator-memory init

# 2. Lưu & Đọc sự thật nguyên tử (L1 Atom)
orchestrator-memory put-atom --key feature_port --value 18098 --agent agent-qa
orchestrator-memory get-atom --key feature_port

# 3. Ghi lại một bài học kinh nghiệm xử lý lỗi (L2 Scenario)
orchestrator-memory put-scenario \
  --id SCN-DOCKER-01 \
  --trigger "Missing Levenshtein on host" \
  --solution "Run tests inside container runtime" \
  --agent agent-coding

# 4. Offload log thô hàng ngàn dòng vào L0
orchestrator-memory offload \
  --node-id TRACE-E2E-01 \
  --summary "E2E benchmark finished in 2.1s" \
  --file /tmp/pytest-output.log \
  --agent agent-qa

# 5. Sinh khối ngữ cảnh phân tầng nén gọn để inject vào prompt
orchestrator-memory inject-context --agent agent-coding
```

### 14.4. Cơ Chế Thu Hoạch Bộ Nhớ Tự Động Qua Watcher (Zero-Manual Auto-Harvest)

> [!TIP]
> **TỰ ĐỘNG HÓA 100% — LOẠI BỎ THAO TÁC GHI NHỚ THỦ CÔNG**:
> Người dùng và Agent **KHÔNG CẦN PHẢI NHỚ GỌI THỦ CÔNG** các lệnh `put-atom`, `put-scenario`, hay `offload`.
> Tiến trình nền `orchestrator-watcher` sẽ tự động đảm nhiệm vai trò **Giám sát Thu hoạch Bộ nhớ (Memory Harvest Watcher)**.

```
┌──────────────────────────────────────────────────────────────────────────┐
│              ORCHESTRATOR WATCHER & AUTO-HARVEST PIPELINE                │
└────────────────────────────────────▲─────────────────────────────────────┘
                                     │ (Tự động kích hoạt khi có Event)
             ┌───────────────────────┴───────────────────────┐
             ▼                                               ▼
  1. Auto-Extract L1 Atoms                       2. Auto-Offload L0 Traces
  - Commit SHA (git rev-parse HEAD)              - qa-results*.json
  - Tests passed/failed counts                   - qa-evidence*.md
  - Container ports từ SESSION_STATE             - *.log (pytest, benchmark)
             │                                               │
             └───────────────────────┬───────────────────────┘
                                     ▼
                        3. Auto-Synthesize L2 Scenarios
                        - Blocker đã gỡ ➔ Giải pháp SOP
                        - Benchmark PASS ➔ Kịch bản kiểm thử
                                     │
                                     ▼
                        4. Auto-Rebuild Mermaid Canvas
                        - Cập nhật symbolic_canvas.mmd tức thì (<50ms)
```

**Cách thức hoạt động ngầm**:
1. Khi sub-agent hoàn thành và phát tín hiệu (`agent-signal finish`, `AGENT_FINISH`), `orchestrator-watcher` lập tức kích hoạt `orchestrator-memory auto-harvest --worktree <WT>`.
2. Trích xuất tự động Commit SHA, số lượng tests pass, container ports vào `l1_atoms.json`.
3. Tự động tìm kiếm các artifacts kiểm thử (`qa-results.json`, `qa-evidence.md`, `*.log`) để offload vào `l0_traces/` và cấp `node_id`.
4. Trích xuất các lỗi đã giải quyết (`current_blocker` ➔ `completed_milestones`) để đúc kết thành bài học trong `l2_scenarios.json`.
5. Tự động dựng lại `symbolic_canvas.mmd`.
6. Khi Orchestrator chuẩn bị dispatch Wave kế tiếp, `orchestrator-memory inject-context` sẽ tự động lấy toàn bộ tri thức này bơm vào prompt cho agent mới mà không tốn một giây thao tác thủ công!
