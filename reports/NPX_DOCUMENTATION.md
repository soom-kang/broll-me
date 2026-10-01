# npx 설치와 pink 비교 샘플 검증

[한국어 README](../README.ko.md)를 열거나 [입력·출력 비교](../docs/assets/pink-demo.html)를 재생하세요.

## 1. Executive Summary

2026-10-01에 현재 checkout, 공식 `skills` CLI 문서, 제공한 영상과 SRT를 확인했습니다. 기존 broll-me 하나를 확장했습니다. 새로운 skill, npm 패키지, test framework는 만들지 않았습니다.

실제 `npx skills add`로 Codex와 Claude Code의 경로를 설치하고, 설치된 엔진으로 `kkumil-pink` 샘플을 만들었습니다. 예정 주소 `soom-kang/broll-me`의 GitHub 게시와 원격 설치 검증은 수행하지 않았습니다.

## 2. Compact Shortlist

| 작업 | 근거 | 기존 자산 | 선택 |
| --- | --- | --- | --- |
| npx 설치 안내 | 사용자 요청; 로컬 CLI 목록에서 skill 1개 발견; 임시 설치 성공 | 단일 canonical skill과 보조 Python 설치기 | 기존 문서와 SKILL 지침 확장 |
| 실제 입력·출력 비교 | 제공한 input과 편집본의 hash 일치; matching SRT와 삽입 기록 확인 | Card template, 팔레트, CLI | 짧은 pink 샘플 재생성 |
| 영문·한글 prompt workflow | 사용자 요청; 기존 문서는 수동 CLI가 중심 | README와 workflow 2개 언어 | 설치부터 전달까지 5단계로 재작성 |

이번 작업은 합의된 개편을 구현했습니다. 최근 30일 전체 업무를 탐색하거나 후보의 빈도와 점수를 새로 추정하지 않았습니다.

## 3. Created or Extended

**Extend Existing: broll-me.** 정본과 이름을 유지했습니다. `SKILL.md`는 설치된 위치를 찾고, 허용된 로컬 렌더링 요청에서 고정 runtime을 준비하는 절차를 명확히 했습니다. 엔진과 runtime source 28개 파일은 변경 전 hash와 같습니다.

README는 비교 GIF를 먼저 보여준 뒤 npx 설치, 프롬프트, 출력 확인을 안내합니다. 영문·한글 workflow는 5단계를 공유하며 수동 CLI와 Python 설치기를 고급 안내로 옮겼습니다. 다이어그램의 문구와 PNG도 맞췄습니다.

| 결과물 | 경로 |
| --- | --- |
| 영문·한글 시작 안내 | [README](../README.md), [README.ko](../README.ko.md) |
| 영문·한글 workflow | [English](../skills/broll-me/reference/workflow.md), [한국어](../skills/broll-me/reference/workflow.ko.md) |
| 비교와 재현 설명 | [비교 페이지](../docs/assets/pink-demo.html), [English sample](../docs/pink-demo.md), [한국어 sample](../docs/pink-demo.ko.md) |
| 영상과 그래픽 | [입력](../docs/assets/pink-demo-input.mp4), [결과](../docs/assets/pink-demo-output.mp4), [card](../docs/assets/pink-demo-card.mp4) |
| 배포물 | [broll-me.skill](../dist/broll-me.skill), [ZIP](../dist/broll-me.zip), [hash manifest](../dist/package-manifest.json) |

샘플은 source frame 1592~1789의 198 frame, 6.6066초입니다. 입력 앞 73 frame은 화자를 유지하고, 뒤 125 frame은 pink card를 표시합니다. 1920×1080과 `30000/1001` FPS를 유지했습니다. 설명용 그래픽이며 실제 제품 화면이나 고객 데이터가 아닙니다.

원본은 보존했습니다. Excerpt 준비 단계에서 영상과 AAC를 한 번 인코딩한 뒤, preview는 excerpt의 오디오를 복사했습니다. 입력·출력의 311개 audio packet은 내용과 timestamp가 같습니다. README GIF만 무음, 가로 1024 px, 10 FPS입니다.

## 4. Deliberately Skipped

새 npm 패키지, engine algorithm 변경, test framework, benchmark, provider 평가와 전역 설치는 제외했습니다. 현재 구조가 npx discovery와 설치를 지원하므로 새 설치기를 만들지 않았습니다. 기존 평가 기록 119개 파일의 hash를 유지했습니다.

기존 full-length preview는 구간 선택에만 참고했습니다. 새 샘플 결과로 표시하거나 배포물에 복사하지 않았습니다.

## 5. Needs More Evidence

GitHub 원격 설치는 저장소 게시 이후 확인해야 합니다. 빈 프로젝트에서 실행할 명령은 다음과 같습니다.

```bash
npx skills add soom-kang/broll-me --list
npx skills add soom-kang/broll-me --skill broll-me --agent codex claude-code
npx skills list --agent codex claude-code
```

사용자의 청취·재생 승인은 대기 상태입니다. 기술 검사로 발화 자막의 의미나 편집 취향까지 승인했다고 보고하지 않습니다. 기존 provider 평가에서는 Claude Code의 fixture 2건이 성공했고, Codex는 Chromium 권한 오류로 차단됐습니다. 이번 로컬 CLI 결과와 구분합니다.

## 6. Validation and Repository Status

Git 저장소가 아닙니다. 처음과 마지막 상태는 `not a git repository`이며, 변경 전 hash 목록으로 범위를 비교했습니다. 관련 없는 사용자 파일과 기존 평가 기록은 보존했습니다.

| 검증 | 결과 |
| --- | --- |
| 로컬 npx 설치, 두 host 경로 | `skills` CLI 1.7.0으로 skill 1개 설치; 같은 정본 참조 |
| Installed CLI doctor | 실제 Chromium `151.0.7922.34` 실행 성공 |
| Pink draft / final | 125 frame씩; scene check와 한글 overflow 검사 통과 |
| Input / output | 각각 198 frame; 6.6066초; decode·FPS·크기 검사 통과 |
| 오디오·원본 | 311 packet의 hash와 timing 일치; 원본 SHA-256 유지 |
| 비교 player | 동시 재생·seek·종료·재시작·단일 오디오 확인; 390 px 화면에서 가로 overflow 없음 |
| 다이어그램 | 영문·한글 self-check 통과; SVG `fit` 480×640, PNG 960×1280 |
| 기존 `make check` | Python 57개, Node 14개 통과 |
| 실패 사례 | Invalid palette가 exit code 2로 실패; HTML을 생성하지 않음 |
| 배포물 | 68개 파일의 curated archive; 재설치·문서 명령의 최소 render 결과는 distribution JSON에 기록 |

첫 offline npx 호출은 npm registry metadata cache가 없어 실패했습니다. 이후 online CLI 확인과 로컬 설치는 성공했습니다. 기본 FFmpeg에 subtitle filter가 없어 해당 시도는 실패했고, 기존 HTML fragment로 자막을 추가했습니다. 자막 시간 반올림과 실제 font 높이도 scene check의 오류를 확인한 뒤 보정했습니다. Diagram의 상대 font URL은 self-check에 맞지 않아 기존 승인된 Google Fonts 방식으로 되돌렸습니다. 실패 로그를 숨기거나 성공으로 바꾸지 않았습니다.

검증 기록: [media](npx-docs-media.json), [visual](npx-docs-visual.json), [diagrams](npx-docs-diagrams.json), [distribution](npx-docs-distribution.json), [review](npx-docs-review.json), [change scope](npx-docs-change-scope.json), [make check](npx-docs-make-check.log).

## 7. Risks, Assumptions and Approvals

`[Assumption]` 배포 예정 주소는 사용자가 지정한 `github.com/soom-kang/broll-me`입니다. 게시가 완료됐다고 가정하지 않습니다. Pink template은 승인된 `card`와 `kkumil-pink`로 구현했습니다.

`[Verified]` 문서의 실행 가능한 bash·JSON 예시는 두 언어에서 같습니다. Npx 재설치는 최종 archive로 수행합니다. Sample footage와 GIF는 `docs/assets/`에 있으며 설치용 archive에는 포함하지 않습니다. MIT, font OFL, icon 고지는 유지했습니다.

`[Unverified]` 새로운 provider별 prompt 실행과 사용자 청취 승인은 이번 범위에서 확인하지 않았습니다. Diagram HTML은 승인된 Google Fonts stylesheet를 사용합니다. 글꼴을 가져올 수 없으면 fallback으로 표시되며, 배포 PNG는 글꼴 다운로드 없이 표시됩니다.

전역 설치, commit, push, GitHub 게시, 외부 미디어 업로드, scheduler 활성화는 수행하지 않았습니다.

## 8. Final Accounting

### Created or Extended

기존 broll-me의 npx 안내와 host prompt 절차를 확장했습니다. 영문·한글 문서와 다이어그램, 재현 가능한 pink 비교 샘플, 갱신한 archive와 검증 기록을 만들었습니다.

### Deliberately Skipped

새 skill·npm 패키지·test framework·engine algorithm 변경·provider 평가·외부 배포를 제외했습니다.

### More Evidence Required

저장소 게시 후 원격 npx 설치 확인, 사용자의 샘플 청취와 시각 승인이 남아 있습니다.
