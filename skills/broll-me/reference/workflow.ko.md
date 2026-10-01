# 설치하고 프롬프트로 B-roll 만들기

작업할 프로젝트에 skill을 설치하세요. Standalone clip과 원본 영상 삽입 모두 아래 5단계로 진행합니다.

[English](workflow.md) · [한국어](workflow.ko.md)

<img src="assets/workflow-ko.png" width="480" alt="설치 → 입력 지정 → 프롬프트 실행 → draft 검토 → 최종 파일 전달">

[다이어그램 HTML](assets/workflow-ko.html)을 수정할 수 있습니다.

1. Skill 하나를 설치합니다.
2. 입력을 지정하고 팔레트를 선택합니다.
3. Codex나 Claude Code에서 프롬프트를 실행합니다.
4. Draft를 검토합니다.
5. 최종 파일을 받습니다.

## 1. Skill 하나 설치하기

예정된 GitHub 저장소가 게시된 뒤에는 작업할 프로젝트에서 실행하세요.

```bash
npx skills add soom-kang/broll-me --skill broll-me --agent codex claude-code
npx skills list --agent codex claude-code
```

GitHub 주소는 예정된 배포 소스이며 게시 여부를 검증하지 않았습니다. 게시 전에는 로컬 checkout이나 ZIP을 푼 폴더의 절대 경로로 바꾸세요.

```bash
npx skills add /path/to/broll-me --skill broll-me --agent codex claude-code
```

압축을 푼 패키지는 `SKILL.md`를 직접 포함하고, checkout은 `skills/broll-me/` 아래에 포함합니다. 목록에는 `broll-me` 하나가 나옵니다. 기본 설치 방식은 `.agents/skills/broll-me`에 정본을 두고 `.claude/skills/broll-me`에서 참조하게 합니다. `--copy`는 host마다 사본을 만듭니다. 로컬 경로는 `skills` CLI `1.7.0`으로 확인했습니다.

이 개발 checkout에 발견 경로가 이미 연결되어 있다면 별도 프로젝트에 설치하세요. 기존 설치를 교체하기 전에는 경로를 확인하세요. `skills`로 설치한 항목을 제거할 때는 이 skill만 지정하세요.

```bash
npx skills remove broll-me --agent codex claude-code
```

`$broll-me`나 `/broll-me`가 보이지 않으면 host의 skill 목록을 새로 불러오거나 새 세션을 시작하세요. 소스를 가져오지 못했다면 설치도 완료되지 않은 것입니다. 존재하는 로컬 폴더로 다시 실행하세요. `npx`에는 Node.js와 npm이 필요합니다. Skill 설치는 렌더링 runtime을 준비하지 않습니다.

## 2. 입력과 팔레트 지정하기

**Standalone**은 목적, 정확한 문구나 chart 수치, 팔레트를 제공하세요. 크기와 길이는 선택 항목입니다. 기본값은 1920×1080, 6초, 30 FPS입니다.

**원본 영상 삽입**은 읽을 수 있는 영상과 같은 영상의 SRT/VTT를 제공하세요. 노트, 안전 영역, 삽입 구간은 선택 항목입니다. Agent는 영상 규격과 자막을 확인하고 삽입 계획을 제시합니다. Speaker box는 추정값이므로 panel을 배치하기 전에 contact sheet를 직접 확인해야 합니다. 자막 cue에서 나눈 word timing도 추정치입니다.

```text
inputs/source.mp4
inputs/source.srt
inputs/notes.json       # optional
```

`warm-orange`가 기본 팔레트입니다. `sage-cream`, `editorial-blue`, `midnight-cyan`, `kkumil-pink`, `onnimm-orange`도 선택할 수 있습니다. 지정한 브랜드나 팔레트가 있으면 기본값보다 우선합니다. Custom JSON은 13개 역할을 모두 `#RRGGBB`로 지정해야 합니다. [팔레트 안내](palettes.md)를 확인하세요. 잘못된 색상이나 대비는 HTML 출력 전에 실패합니다.

렌더링 전에 아래 실행 파일을 준비하세요. Setup은 시스템 도구를 설치하지 않습니다. 기본 실행 파일의 버전이 다르면 맞는 경로를 지정하세요.

| 구성 요소 | 필수 버전 |
| --- | --- |
| Node.js | `24.21.0`, npm 포함 |
| Python | `3.12.14` |
| FFmpeg / FFprobe | `9.0.2`, `libx264`, `prores_ks` 포함 |
| 로컬 module | Playwright `1.62.1`, NumPy `2.3.5` |
| Chromium | Revision `1234`, version `151.0.7922.34` |

Agent는 설치된 `SKILL.md` 위치를 찾고 `doctor`를 실행합니다. 준비된 runtime은 재사용합니다. 로컬 렌더링이 승인된 작업이고 실행 파일의 버전이 맞으면 `setup.sh`로 module과 Chromium을 프로젝트 내부에 설치할 수 있습니다. 전역 설정은 변경하지 않습니다. 실행 파일 누락, 버전 불일치, browser 권한 오류가 나면 실제 오류와 다음 행동을 보고합니다. [Runtime 복구](troubleshooting.md#runtime-and-browser)를 참고하세요.

## 3. 프롬프트 실행하기

Codex에서는 `$broll-me`, Claude Code에서는 `/broll-me`로 시작한 뒤 같은 요청을 붙이세요. 프로젝트 밖의 파일은 읽을 수 있는 절대 경로를 사용하세요.

```text
inputs/source.mp4와 같은 영상의 inputs/source.srt를 읽어 주세요.
inputs/notes.json이 있으면 함께 참고해 주세요. kkumil-pink 팔레트로
색소 배합과 시술 사진을 설명하는 짧은 card cutaway를 만들어 주세요.
도입부의 화자는 그대로 보여 주세요. 자막을 보고 삽입 시간을 제안한 뒤
draft를 보여 주세요. 원본을 보존하고 preview에는 원본 오디오를 복사해 주세요.
최종 clip, preview.mp4, viewer.html, compare.html, TIMING.md를
motion/out에 저장해 로컬에서 확인할 수 있게 해 주세요.
```

Standalone은 다음처럼 요청하세요.

```text
kkumil-pink 팔레트로 6초 한글 card를 만들어 주세요.
제목: 지난 시술 기록을 한눈에
본문: 색소 배합, 시술 사진
draft를 보여 준 뒤 최종 MP4와 팔레트 snapshot을 전달해 주세요.
```

Agent는 공통 CLI와 [장면 템플릿](scenes.md)을 사용합니다. Card와 panel에는 `title`, `body`가 필요합니다. Terminal은 `title`, `lines`, chart는 `title`과 제공된 비음수 `bars` 값을 사용합니다. Custom HTML이 필요할 때만 [엔진 API](engine-api.md)를 읽습니다. 수치, 고객 기록, 인용한 발화를 임의로 만들지 않습니다.

승인된 문구, 팔레트, 삽입 구간은 재사용하세요. 새로 정할 사항에 승인이 필요한 작업이면 먼저 확인합니다. 자막이나 노트, 이전 렌더링 결과만으로 승인되었다고 판단하지 않습니다.

## 4. Draft 검토하기

Draft와 주요 frame을 여세요. 한글 가독성, 대비, cutaway timing, 전환을 확인하세요. 투명 panel은 구간 전체에서 화자를 가리지 않아야 합니다. 바꿀 시간이나 문구를 agent에게 알려 주세요.

Draft는 frame당 한 번 캡처하며 motion blur를 생략합니다. Final은 4개 subframe에 motion blur를 적용합니다. 크기, FPS, frame 수, container, alpha 동작은 같습니다. Draft는 검토용이므로 전달할 결과에는 final 렌더링을 요청하세요.

`check`는 scene 계약, 표본 시점의 browser 오류, template text overflow를 검사합니다. 재생 확인도 필요합니다. 글자가 잘리면 문구를 줄이거나 장면을 나눈 뒤 다시 build하세요. Browser나 encoder 오류는 CLI JSON과 stderr에서 확인하고 원인을 고친 뒤 해당 단계만 재실행하세요. 이전 결과는 보존합니다.

## 5. 최종 파일 받기

Standalone은 최종 MP4나 alpha MOV, scene HTML, 팔레트 snapshot, 주요 frame을 받습니다. 영상이 없으면 원본 검사나 오디오 보존을 완료했다고 보고하지 않습니다.

원본 영상 작업은 `preview.mp4`, `viewer.html`, `compare.html`, `TIMING.md`도 받습니다. 전체 화면 card는 MP4와 `kind:full`을 사용합니다. Panel은 `bg:null`을 유지하며 ProRes 4444 MOV와 `kind:panel`을 사용합니다. 검토 페이지가 참조하는 clip과 입력 파일의 경로를 유지하세요. Preview로 삽입을 검토하고, 최종 master는 편집자가 승인합니다.

Shared font HTML은 옆의 `assets/broll-me-fonts/` 폴더와 함께 전달하세요. Build나 preview에서 `--font-mode embedded`를 선택하면 개별 HTML을 파일 하나로 전달할 수 있습니다. 두 방식 모두 font 고지를 유지합니다.

Preview는 원본 파일을 보존하고 audio stream을 복사합니다. Video와 audio가 0에서 시작해야 하며, audio는 video 길이 안에 들어오고 MP4와 호환되어야 합니다. 지원하지 않는 timing이나 codec은 실패합니다. 승인된 호환 입력 사본을 제공하거나 별도 오디오 편집을 진행하세요. Skill은 복구를 위해 원본 오디오를 임의로 정규화하거나 자르거나 변환하지 않습니다. 삽입 구간이 clip보다 길면 마지막 frame을 끝까지 유지합니다.

전달 파일, 팔레트, 실제 검사, 중단된 작업, 남은 재생 승인을 보고하세요. 기존 host 평가에는 Claude Code fixture 성공과 Codex Chromium 권한 차단이 기록되어 있습니다. 로컬 CLI 성공으로 해당 provider 결과를 바꾸지 않습니다.

## 고급: runtime 직접 준비하기

실제 설치 폴더를 찾으세요. 아래 경로는 `npx skills`의 기본 프로젝트 설치에 맞습니다. 소스 checkout에서는 Python 설치기로 두 host를 `skills/broll-me`에 연결할 수도 있습니다. 개발용 보조 경로입니다.

```bash
export BROLL_SKILL_DIR="$PWD/.agents/skills/broll-me"
export BROLL_RUNTIME="$PWD/motion"
```

Runtime은 `--runtime PATH`, `BROLL_RUNTIME`, `./motion` 순서로 선택합니다. 필요하면 `BROLL_NODE`, `BROLL_PYTHON`, `BROLL_FFMPEG`, `BROLL_FFPROBE`, `BROLL_NPM`에 고정 버전의 실행 파일 경로를 지정하세요. Setup 전에 버전과 encoder를 확인하세요.

```bash
"${BROLL_NODE:-node}" --version
"${BROLL_PYTHON:-python3}" --version
"${BROLL_FFMPEG:-ffmpeg}" -version
"${BROLL_FFPROBE:-ffprobe}" -version
"${BROLL_FFMPEG:-ffmpeg}" -hide_banner -encoders
```

고정 버전과 필수 encoder 2개를 확인하세요. 다르면 맞는 경로를 선택한 뒤 진행합니다. Setup은 로컬 Python virtualenv, NumPy, Node module, Chromium을 설치하며 시스템 실행 파일은 설치하지 않습니다.

```bash
bash "$BROLL_SKILL_DIR/scripts/setup.sh" "$BROLL_RUNTIME"
python3 "$BROLL_SKILL_DIR/scripts/broll.py" doctor
```

`status:completed`, `ready:true`가 나오면 준비된 상태입니다. Doctor는 browser를 실제 실행하고 override를 포함한 버전을 검사합니다. 준비된 runtime이 있으면 `BROLL_RUNTIME`을 지정하고 setup을 생략하세요. 이 개발 checkout의 `.runtime/motion`은 배포물에 포함하지 않습니다.

## 고급: standalone 직접 렌더링하기

작은 장면 하나를 작성한 뒤 build, check, render를 실행하세요.

```bash
mkdir -p motion
cat > motion/scene.json <<'JSON'
{
  "schema_version": 1,
  "template": "card",
  "title": "Choose a palette",
  "body": "Keep the motion. Change the colors.",
  "width": 640,
  "height": 360,
  "duration": 1
}
JSON
python3 "$BROLL_SKILL_DIR/scripts/broll.py" build motion/built \
  --scene motion/scene.json --palette kkumil-pink
python3 "$BROLL_SKILL_DIR/scripts/broll.py" check motion/built/scene.html
python3 "$BROLL_SKILL_DIR/scripts/broll.py" render \
  motion/built/scene.html motion/out/scene-draft.mp4 --quality draft
python3 "$BROLL_SKILL_DIR/scripts/broll.py" render \
  motion/built/scene.html motion/out/scene.mp4 --quality final
```

`scene.html`, `palette.resolved.json`, shared font와 MP4 2개가 생성됩니다. 입력이 잘못되면 표시된 field를 고치세요. 다른 팔레트는 새 build 폴더를 사용하세요. 필요하면 `--fps 30000/1001`을 추가합니다. 기본 렌더링은 30 FPS입니다. Alpha는 panel scene과 `.mov`를 사용하세요. Beats, inspect 등은 [CLI 사용법](usage.md)을 참고하세요.

## 고급: 삽입 preview 직접 만들기

장면 작성 전에 원본과 자막을 확인하세요.

```bash
python3 "$BROLL_SKILL_DIR/scripts/broll.py" inspect inputs/source.mp4 motion/work
python3 "$BROLL_SKILL_DIR/scripts/broll.py" words inputs/source.srt
```

`video.json`, `contact.png`, 추정 word time이 출력됩니다. 검사한 width, height, FPS로 승인된 장면을 build, check, render하세요. Plan에 경로와 승인된 시간을 넣습니다. 상대 경로는 plan 파일을 기준으로 해석합니다.

```json
{
  "video": "../inputs/source.mp4",
  "fps": "30000/1001",
  "clips": [{
    "id": "01",
    "title": "Approved card",
    "line": "Exact supplied subtitle text",
    "file": "out/scene.mp4",
    "kind": "full",
    "in": 1,
    "out": 3
  }],
  "notes": ["Illustrative graphic; not a product screen."]
}
```

예시에는 3초 이상의 영상이 필요합니다. 검사한 원본과 승인된 plan에 맞게 시간과 FPS를 바꾼 뒤 실행하세요.

```bash
python3 "$BROLL_SKILL_DIR/scripts/broll.py" preview motion/plan.json motion/out/preview.mp4
```

Preview, HTML 검토 페이지, timing 문서, shared font가 생성됩니다. 파일 누락, clip 겹침, 범위를 벗어난 시간은 실패합니다. Plan을 고치고 다시 실행하세요. 오디오나 encoder 오류는 [Media 복구](troubleshooting.md#media-and-delivery)를 참고하세요.

## 고급: archive와 개발용 설치

`broll-me.zip`이나 ZIP 형식의 `.skill`을 푸세요. `broll-me/SKILL.md`가 있는 상위 폴더 또는 해당 `broll-me` 폴더를 `npx skills add`에 지정하세요. Runtime과 영상은 포함하지 않습니다.

Checkout의 Python 설치기는 개발용 보조 경로입니다. Checkout root에서 실행하세요.

```bash
python3 scripts/install_skill.py --project /path/to/project --host both --dry-run
python3 scripts/install_skill.py --project /path/to/project --host both
```

정본 하나를 참조하는 상대 링크 2개를 만듭니다. 같은 링크가 있으면 `already installed`를 출력하고, 다른 경로와 충돌하면 교체 없이 exit code `1`로 끝납니다. Python 설치기로 만든 링크는 출력된 `unlink` 명령으로만 제거하세요. 이 방법으로 `npx`의 정본 디렉터리를 제거하지 마세요.
