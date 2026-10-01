# broll-me 문서 정리 결과

[영문 README](../README.md) 또는 [한국어 README](../README.ko.md)를 열어 첫 실행을 진행하세요. 문서와 배포물 정리는 완료했으며 엔진 알고리즘은 유지했습니다.

## 1. Executive summary

이번 확정 계획과 현재 workspace를 조사했습니다. 최근 30일의 별도 workflow discovery는 수행하지 않았습니다. 새 skill, custom agent, automation은 만들지 않고 기존 `broll-me` 하나의 문서와 평가 도구, 배포물을 확장했습니다.

영문을 기본으로 README와 workflow를 작성하고 한글 문서를 함께 제공했습니다. 타이틀 이미지 1개와 영문·한글 다이어그램 PNG, 수정 가능한 HTML을 추가했습니다. 이전 비교 기록과 source snapshot, 기록에 명시된 작업용 임시 checkout 및 evaluation sandbox를 정리했습니다. 삭제한 내용을 새 backup에 복사하지 않았습니다.

## 2. Compact shortlist

이번 계획의 단일 자산 확장만 처리했습니다. 빈도나 날짜가 확인되지 않은 후보를 추가하지 않았습니다.

| Priority | Workflow | Evidence | Coverage | Recommendation |
| --- | --- | --- | --- | --- |
| 1 | 팔레트 기반 B-roll의 설치, 제작, 검토와 전달 | 승인한 문서 계획, 현재 CLI, 2026-10-01 fixture 및 archive 실행 | 기존 `broll-me` | 문서와 기존 도구 확장 |

## 3. Created or extended

정본은 `skills/broll-me/`입니다. Codex와 Claude Code의 기존 발견 경로는 같은 정본을 계속 참조합니다. 다른 skill 설치 항목은 추가하지 않았습니다.

| Files | Result |
| --- | --- |
| `README.md`, `README.ko.md` | 이미지, 설치, 준비 조건, 첫 출력, 실패 후 행동 |
| `reference/workflow.md`, `workflow.ko.md` | Standalone과 원본 영상 삽입의 5단계; 명령과 출력, 오류 계약 일치 |
| `SKILL.md`, 연결된 reference | 영문 기본, 공통 CLI와 필요한 단계의 상세 문서 연결 |
| `reference/assets/` | `broll-me-title.png`, `workflow-en.png`, `workflow-ko.png` 및 두 HTML 원본 |
| Repository scripts | `with_skill` 평가만 지원, 현재 검토 화면 기본값, 지정 PNG 3개만 패키지 허용 |

MIT 저작권·허가 문구와 font·icon 고지는 보존했습니다. License footer의 font 경로만 현재 구조로 정리했습니다. HyperFrames는 workflow 영감으로만 기록했습니다. 처음부터 작성한 엔진이나 코드 영향이 없다는 주장은 추가하지 않았습니다.

현재 `iteration-2`의 command, execution, artifact manifest와 렌더링 결과, grading은 유지했습니다. 소스 문구가 포함된 Codex host transcript 2개를 제거했고, 오래된 비교 통계 항목은 정리했습니다. 삭제한 임시 sandbox를 가리키는 과거 execution 경로는 더 이상 존재하지 않습니다. 과거 grading은 다시 실행하지 않았으며 fixture 사본은 `.verification/improvements/fixtures/`에 있습니다.

## 4. Deliberately skipped

추가 모델 평가와 description 최적화, 엔진 재작성, 대형 검증 framework는 수행하지 않았습니다. 새 test 파일이나 runtime dependency도 추가하지 않았습니다. 전역 설치, commit, push, 외부 배포, scheduler 활성화는 수행하지 않았습니다.

## 5. Needs more evidence

Codex의 Chromium 권한 차단 이후 render·preview 실행, 실제 영상의 발화 동기화와 speaker 안전 영역, 사용자 시각 승인은 미완료입니다. 기존 Claude Code fixture 2건은 완료했고 palette-switch 11/11, panel 9/9 assertion을 통과했습니다. Codex 2건은 `blocked`이며 품질 점수가 없습니다. 이번 문서 검증을 새 host 평가로 계산하지 않습니다.

## 6. Validation and repository status

초기와 최종 환경 모두 Git 저장소가 아닙니다. 현재 파일 hash와 엔진·CLI의 변경 전 hash로 범위를 확인했습니다. 기존 현재 실행의 manifest 소유 산출물은 변경하지 않았습니다.

| Check | Result | Evidence |
| --- | --- | --- |
| Existing `make check` | Python 57개, Node 14개 통과 | `documentation-make-check.log` |
| Language parity | 양쪽 README·workflow의 bash, JSON, text 예제 일치 | `documentation-links.json` |
| Diagram self-check | 두 HTML 통과 | `documentation-assets.json` |
| Diagram browser check | 480×640, PNG 960×1280, font 로드, 390 px local scroll, page overflow 없음 | `documentation-visual-validation.json` |
| README literal commands | doctor, build, check, draft·final render 완료; 각 1초, 30 frame | `.verification/documentation/first-run/stdout.jsonl` |
| Package edge cases | 임의 PNG 거부; 미지원 configuration은 exit `2`; provider 호출 없음 | `documentation-validation.json` |
| Current review UI | 기존 검사 5개 통과 | `documentation-review-page-validation.json` |
| Archive reinstall | 새 archive의 project link 2개, 정본 1개, 최소 final render 및 decode 통과 | `documentation-distribution-validation.json` |
| Writing review | GitHub Markdown 규칙, stop-slop, 한글 style/grammar/humanizer 수동 검토 | `documentation-style-review.json` |
| Cold read | 독립 reviewer 1회, P2 준비 조건 누락 지적; 두 언어에 보완 | `documentation-cold-review.json` |

Cold read의 원래 판정은 `gaps_present`였습니다. 고정 실행파일이 준비된 환경을 시작 조건으로 명시하고 실행파일 버전과 FFmpeg encoder 확인 명령을 추가했습니다. 수정 후 확인은 작성자 검토이며 두 번째 독립 review를 실행하지 않았습니다.

처음 PNG export에 사용한 Python에는 Playwright module이 없어 해당 명령이 실패했습니다. 이미 준비된 Node Playwright로 동일한 SVG 영역을 내보냈으며 dependency는 설치하지 않았습니다. Archive 검사의 첫 시도는 `/var`와 `/private/var`의 경로 표기 차이를 같은 경로로 비교하지 못해 실패했습니다. 검사 사본에서 양쪽을 resolve한 뒤 재설치와 렌더링을 통과했습니다. 두 문제는 검증 실행 방식의 수정이며 엔진 변경이 아닙니다.

재실행 명령은 다음과 같습니다. Chromium browser 검사는 실행 가능한 local 권한 환경이 필요하며 host의 권한 정책을 우회하지 않습니다.

```bash
make check BROLL_NODE=/Users/soom.kang/.nvm/versions/node/v24.21.0/bin/node
python3 scripts/validate_package.py --archive dist/broll-me.skill
.runtime/dev/bin/python scripts/package.py --require-creator
python3 /Users/soom.kang/.agents/skills/diagram-design/scripts/self_check.py \
  skills/broll-me/reference/assets/workflow-en.html
python3 /Users/soom.kang/.agents/skills/diagram-design/scripts/self_check.py \
  skills/broll-me/reference/assets/workflow-ko.html
```

## 7. Risks, assumptions and approvals

`[Verified]` 현재 문서용 fixture와 archive 검사는 local 실행 근거입니다. 엔진·CLI hash는 변경 전과 같습니다. 재배포 고지는 보존했습니다.

`[Assumption]` 사용 가이드는 명시된 고정 버전의 시스템 실행파일이 준비된 환경에서 시작합니다. 준비되지 않았다면 프로젝트 담당자에게 matching executable 또는 runtime을 요청해야 합니다. 실영상 삽입은 검사한 규격과 승인된 slot을 사용합니다.

`[Unverified]` 사용자의 실제 영상에 대한 동기화, 최종 편집과 시각 승인은 아직 검증하지 않았습니다. 문서 cold read와 표본 frame 확인은 이를 대신하지 않습니다. 외부 활성화는 수행하지 않았으며 이번 작업에 추가 승인이 필요한 변경은 남지 않았습니다.

## 8. Final accounting

### Created or extended

기존 `broll-me`의 문서, 평가 도구와 packaging 정책을 확장했습니다. [broll-me.skill](../dist/broll-me.skill), [ZIP](../dist/broll-me.zip), [hash manifest](../dist/package-manifest.json)를 다시 만들었습니다. Archive에는 정본 파일 68개와 지정 문서 이미지 3개가 포함됩니다.

### Deliberately skipped

추가 모델 평가, 새 asset 유형, 전역 설치와 외부 배포를 제외했습니다.

### More evidence required

Codex의 차단 이후 실행과 실영상 편집 검토, 사용자 시각 피드백이 필요합니다. 현재 범위의 문서·기록 정리와 배포 검증은 완료했습니다.
