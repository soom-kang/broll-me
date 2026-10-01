# broll-me engine improvements

Recorded: 2026-10-01, Asia/Seoul. 이번 보고서는 승인된 개선 계획의 구현과 직접 실행 근거를 다룬다. 최근 30일의 새로운 workflow discovery나 대규모 benchmark 결과로 표현하지 않는다.

## Executive Summary

기존 `broll-me` 하나를 확장했다. 새 skill·custom agent·automation 자산은 생성하지 않았다. 공통 CLI, SceneSpec 4종, 공유 font, draft rendering과 검사를 추가했고, 평가 산출물 혼합·두 번째 palette 미검사·browser override 버전 미검사 결함을 수정했다. 새로운 runtime dependency는 추가하지 않았다.

Claude Code의 대표 요청 두 건은 실제 fixture의 검사부터 영상·preview·검토 페이지 출력까지 완료했다. Codex는 두 건 모두 skill을 읽고 공통 `doctor`를 실행했으나 Chromium MachPort 권한 오류로 `blocked`다. Codex의 렌더링 이후 과정과 양쪽 host의 품질 우열은 확인되지 않았다. 전체 provider 호출은 승인된 4회뿐이다.

## Created or Extended

| Asset | Form | Scope | Evidence |
| --- | --- | --- | --- |
| `broll-me` | Extend Existing | 팔레트 기반 motion B-roll author/build/check/render/preview | 승인 계획, 현재 source, 로컬 media 검사, iteration-2 실제 host 실행 |

정본은 `skills/broll-me/`다. Codex `.agents/skills/broll-me`와 Claude `.claude/skills/broll-me`는 기존 상대 symlink로 같은 정본을 참조한다. 별도 skill 설치 항목을 추가하지 않았다.

- `scripts/broll.py`: 표준 라이브러리 진입점. Runtime 선택 순서, executable override, stdout 단일 JSON과 nonzero exit code를 유지한다.
- `engine/scene_templates.py`, `examples/scenes/`: card·terminal·chart·panel을 기존 fragment로 변환한다. 문구 escaping, 실제 제공 수치, semantic palette와 panel `bg:null`을 유지한다.
- `engine/fonts.py`, build·review pages: 새 CLI의 shared 기본값, 기존 직접 호출의 embedded 기본값. 동일 font·OFL notice 재사용, 다른 기존 파일·symlink 덮어쓰기 거부.
- `motion.js`, `check.js`: DOM 변경 전 scene 참조·geometry·timing·cursor 검증, 주요 시점 browser 오류와 보이는 template 텍스트 overflow 검사. Custom HTML의 의도적인 색상과 callback은 유지한다.
- `render.js`: final 4 subframe과 draft 1 screenshot. 동일 resolution·FPS·frame 수·container·alpha 계약을 유지한다. 속도 향상 배수는 측정·주장하지 않았다.
- `scripts/runtime/browser_check.js`, `setup.sh`: 선택 browser 실제 실행과 정확한 version 검사. Override도 고정 profile을 통과해야 한다.
- 공통 `SKILL.md`, `agents/openai.yaml`, reference: 공통 CLI·템플릿·단계별 reference로 정리하고 host 전용 질문 도구나 shell substitution을 요구하지 않는다.
- Repository 평가 도구: iteration/UUID별 산출물과 SHA-256 manifest 소유 파일만 채점. 두 palette의 snapshot·CSS·JS를 각각 검사한 후 geometry·timing을 비교한다. 평가자는 host 영상을 재렌더링하지 않는다.
- `scripts/create_review.py`: 설치된 skill-creator viewer를 유지하면서 embedded JSON을 escape하고, 점수 없는 실행을 quality table에서 제외한다. 원본 평가 JSON은 보존한다.

## Validation and Repository Status

Git 저장소가 아니다. 문서 정리 과정에서 오래된 비교 기록과 snapshot을 삭제했다. 현재 배포 파일 hash는 `../dist/package-manifest.json`에서 확인한다. 아래 검증 표는 엔진 개선 당시의 실행 근거이며, 문서 변경 이후 검증은 [documentation report](DOCUMENTATION.md)를 따른다. 현재 실행 결과와 산출물 manifest는 보존했다.

| Check | Actual result | Evidence |
| --- | --- | --- |
| `make check` | Python 57, Node 14 통과; package 61 files 검사 | `improvement-make-check.log` |
| Common CLI invalid input | unknown/exclusive palette, missing SceneSpec/input이 명확한 nonzero·단일 JSON으로 실패 | `improvement-cli-validation.json` |
| MP4/MOV final·draft | 각 30 frames, 640×360, `30000/1001`; 4 outputs decode 통과, 두 MOV alpha 0–255 | `improvement-media-validation.json` |
| Preview | 1초 clip을 2초 slot에 hold; 두 preview 120 frames·4.004초; source hash·audio packet hash 보존 | same report |
| Shared font | 같은 scene HTML 19,007 bytes, embedded 14,066,612 bytes; font는 별도 전달. 공백·특수문자 directory 이동 후 check 통과 | same report |
| Palette switch | warm-orange/cyan 각각 snapshot·CSS·JS 확인; scene·geometry·timing 동일, pixel 결과 다름 | same report |
| Source review | CLI·template·font·build·pages의 bounded read-only review에서 supported defect 없음 | `improvement-source-review.json` |
| Review UI | 실제 browser에서 점수 표시와 shared Hangul font 확인 | `improvement-review-validation.json` |
| Distribution | skill-creator packaging·exact archive 검증·임시 프로젝트 양쪽 발견 경로 설치·최소 final render/decode 통과 | `improvement-distribution-validation.json` |

검증 코드는 기존 것을 재사용하고 결함·신규 입력에 해당하는 focused 사례만 추가했다. 별도 대형 framework나 description 최적화 loop는 만들지 않았다. 최초 preview fixture는 필수 clip title을 빠뜨려 실패했고 fixture를 바로잡았다. 최초 review-font 검사는 ASCII 문구에서 한글 font가 자동 로드된다고 가정해 실패했으며, 한글 glyph를 명시적으로 요청해 실제 asset 로드를 확인했다. 두 수정은 engine 변경이 아니다. 제한된 root sandbox에서의 Chromium launch 실패도 숨기지 않았으며, 허용된 로컬 실행 환경에서 media 검증을 완료했다.

## Actual Host Evaluation

| Host | Request | Execution | Quality assertions |
| --- | --- | --- | --- |
| Codex | palette-switch | `blocked`: doctor의 Chromium MachPort permission failure | 점수 없음 |
| Codex | ONNIMM transparent panel | same environment block | 점수 없음 |
| Claude Code | palette-switch | 실제 output 완료 | 11/11 |
| Claude Code | ONNIMM transparent panel | 실제 output 완료 | 9/9 |

이번 환경에서는 Claude 로그인 차단이 발생하지 않았다. 초기 보고서의 과거 authentication 상태를 현재 상태로 재사용하지 않는다. Codex의 `workspace-write` sandbox를 유지했으며 자동으로 권한을 우회하거나 재시도하지 않았다. `blocked`, timeout, ordinary failure는 quality score와 분리한다.

실제 파일·명령·manifest·grading은 `../skills/broll-me-workspace/iteration-2/`에 있다. 요약은 `model-evaluations-iteration-2.json`, `model-benchmarks-iteration-2.json`, 검토 화면은 [improvement-review.html](improvement-review.html)이다. 사람이 검토한 승인 결과는 아직 없다. 정리된 임시 sandbox의 경로는 더 이상 존재하지 않는다. 기존 grading은 재실행하지 않았으며 command·artifact manifest와 렌더링 결과를 보존했다. 원본 fixture 사본은 `.verification/improvements/fixtures/`에 있다.

Codex의 browser 실행 권한이 해결된 뒤 다음 명령으로 차단된 두 요청만 새 iteration에서 다시 실행할 수 있다. 이 명령은 이번 작업에서 실행하지 않았다.

```bash
python3 scripts/run_evals.py --provider codex --eval-ids 1 3 --configuration with_skill --iteration 3 --boundary end-to-end --source-video .verification/improvements/fixtures/source.mp4 --srt .verification/improvements/fixtures/transcript.srt --vtt .verification/improvements/fixtures/transcript.vtt --runtime .runtime/motion --python /Users/soom.kang/Desktop/work/2.services/broll-me/.runtime/motion/.venv/bin/python --node /Users/soom.kang/.nvm/versions/node/v24.21.0/bin/node --timeout 360 --workers 2
```

## Risks, Assumptions and Approvals

- `[Verified]` 위 결과는 synthetic fixture와 이번 실행 파일을 기준으로 한다. 실제 발화 alignment·speaker 안전 영역·사용자의 편집 취향은 검증되지 않았다.
- `[Assumption]` 원본 삽입 시 source 검사 규격과 승인된 slot을 사용한다. SceneSpec의 standalone 기본값은 1920×1080·6초·30 FPS다.
- Fixed runtime 버전, MIT·Geist/Noto OFL·icon notice를 보존한다. Private 브랜드 이미지·로고, runtime, 평가 파일은 배포물에 포함하지 않는다.
- 전역 설치·commit·push·외부 배포·scheduler activation은 수행하지 않았다. 프로젝트 발견 경로는 이미 설치된 같은 정본을 계속 사용한다.

## Final Accounting

### Created or Extended

기존 `broll-me` skill 1개 확장. `dist/broll-me.skill`, ZIP과 hash manifest 재생성. 이번 평가용 보고서·검토 화면 생성.

### Deliberately Skipped

대규모 benchmark, description 최적화, baseline provider 추가 실행, 병렬 rendering, frame cache, font subset, 다른 skill·agent·automation 자산, 전역 설치와 외부 배포.

### More Evidence Required

Codex sandbox의 output 단계 실행, 실제 영상의 발화·배치·전환 검토, 사용자 시각 피드백. 이 항목을 완료한 것으로 표시하지 않는다.
