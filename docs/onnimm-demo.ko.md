# ONNIMM 적용 전후 샘플

[English](onnimm-demo.md) · [한국어](onnimm-demo.ko.md) · [README로 돌아가기](../README.ko.md)

카페 대화 영상에 `onnimm-orange` 모션 그래픽을 넣은 예시입니다. 시술 기록, 동의 이력, 정보 접근 범위를 설명합니다. 실제 제품 화면이나 고객 기록이 아닌 설명용 그래픽입니다.

## 비교 영상 보기

- [입력 MP4](assets/onnimm-context-input.mp4)
- [결과 MP4](assets/onnimm-context-output.mp4)
- [동시 재생 비교 페이지](assets/onnimm-context.html)
- [B-roll 7장면 전체 · 42.509초](assets/onnimm-highlights.html)

HTML과 MP4를 같은 폴더에 두고 HTML을 로컬에서 여세요. 두 영상을 함께 재생하며, 소리는 결과 영상에서만 나옵니다. README의 GIF는 각각 재생되므로 시작이 조금 어긋날 수 있습니다.

적용 결과는 화자 5.005초 → 동의 이력 그래픽 7.841초 → 화자 5.005초 순서입니다.

## 샘플 규격

| 항목 | 값 |
| --- | --- |
| 원본 프레임 | 1972~2506, 양 끝 포함 |
| 원본 시간 구간 | 01:05.799~01:23.650 |
| 비교 구간 길이 | 17.851초 |
| 입력·결과 MP4 | 각각 535프레임, 1920×1080, `30000/1001` FPS |
| README의 GIF | 같은 구간, 480×270, 10 FPS, 무음 |
| 팔레트 | `onnimm-orange` |

제공된 broll-me 제작 미리보기에서 네 번째 삽입 장면을 포함한 구간을 추출했습니다. 문서용 발췌이며, 새로 수행한 호스트 실행 테스트는 아닙니다.

두 영상에는 원본에서 잘라 AAC로 인코딩한 같은 발화를 넣었습니다. 원본 영상과 제공된 미리보기는 변경하지 않았습니다. [프레임 범위와 해시](assets/onnimm-context.json), [전체 장면 메타데이터](assets/onnimm-highlights.json)를 확인할 수 있습니다.

## 내 영상에 적용하기

[사용 가이드](../skills/broll-me/reference/workflow.ko.md)에 따라 스킬과 실행 환경을 준비하세요. 작업 프로젝트의 `inputs/`에 영상과 같은 영상의 자막을 넣은 뒤 Codex에서 다음과 같이 요청하세요.

```text
$broll-me를 사용해 inputs/source.mp4와 같은 영상의 inputs/source.srt를 읽어 주세요.
inputs/notes.json이 있으면 함께 참고해 주세요. onnimm-orange 팔레트로
시술 기록, 동의 이력, 정보 접근 범위를 설명하는 짧은 B-roll을 만들어 주세요.
삽입 구간 사이에는 화자를 보여 주세요. 자막에서 문구와 삽입 구간을 제안한 뒤
초안을 보여 주세요. 원본을 보존하고 미리보기에는 원본 오디오를 복사해 주세요.
최종 클립, preview.mp4, viewer.html, compare.html, TIMING.md를
outputs/onnimm-cafe-broll에 저장해 주세요.
```

Claude Code에서는 `$broll-me` 대신 `/broll-me`를 사용하세요. 주제와 파일 경로는 자신의 영상에 맞게 바꾸세요. 샘플과 같은 작업 흐름을 사용하는 요청이며, 장면의 배치까지 똑같이 재현하는 프롬프트는 아닙니다.

장면 소스와 수동 재현 명령이 필요하면 [핑크 카드 예제](pink-demo.ko.md)를 참고하세요.
