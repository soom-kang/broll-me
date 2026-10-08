![broll-me: 같은 모션 그래픽에 여러 팔레트 적용](skills/broll-me/reference/assets/broll-me-title.png)

[English](README.md) · [한국어](README.ko.md)

# broll-me

**모션 그래픽 B-roll을 만드는 Codex·Claude Code용 스킬입니다.**

문구, 데이터 또는 자막이 있는 영상을 바탕으로 움직이는 카드, 터미널, 차트, 투명 패널을 만듭니다. 편집기에 넣을 영상 클립과 수정 가능한 HTML 장면, 검토 파일을 함께 제공합니다.

## 왜 필요한가요

인터뷰나 설명 영상을 편집하다 보면 말로만 전달하기 어려운 내용을 자료화면으로 보여 줘야 합니다. 짧은 장면 하나에도 문구 정리, 그래픽 디자인, 애니메이션, 발화에 맞춘 삽입 작업이 필요합니다. 여러 장면의 스타일까지 맞추려면 같은 작업을 반복하게 됩니다.

broll-me는 이 과정을 하나의 프롬프트 흐름으로 연결합니다. 장면과 삽입 시간을 제안하고, 선택한 팔레트로 그래픽을 만든 뒤, 초안 검토를 거쳐 최종 파일을 렌더링합니다. 문구와 배치, 최종 편집은 편집자가 결정합니다.

## 적용 전후

| Input · 원본 영상                                                                                                       | Output · broll-me 적용 결과                                                                                                      |
| ----------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| [![입력 프리뷰: 구간 내내 카페에서 말하는 화자](docs/assets/onnimm-context-input.gif)](docs/assets/onnimm-context.html) | [![결과 프리뷰: 같은 화자, 동의 이력 그래픽, 다시 화자](docs/assets/onnimm-context-output.gif)](docs/assets/onnimm-context.html) |
| [입력 MP4 보기](docs/assets/onnimm-context-input.mp4)                                                                   | [결과 MP4 보기](docs/assets/onnimm-context-output.mp4)                                                                           |

같은 17.851초 구간을 비교합니다. 적용 결과에는 동의 이력 그래픽이 잠깐 나온 뒤 다시 화자로 돌아옵니다. 설명용 그래픽이며 실제 제품 화면이나 고객 기록은 아닙니다.

[비교 페이지](docs/assets/onnimm-context.html)를 MP4 파일과 함께 로컬에서 열면 두 영상을 맞춰 재생할 수 있습니다. 소리는 결과 영상에서만 나옵니다. GitHub의 GIF는 각각 재생됩니다. [B-roll 7장면 보기](docs/assets/onnimm-highlights.html) · [샘플 상세 정보](docs/onnimm-demo.ko.md)

## 빠른 시작

### 1. 설치

스킬을 사용할 프로젝트에서 실행하세요. `npx`를 사용하려면 Node.js와 npm이 필요합니다.

```bash
npx skills add https://github.com/soom-kang/broll-me/tree/v0.8.0-beta.2 --skill broll-me --agent codex claude-code
```

**`v0.8.0-beta.2` 베타 버전**을 설치합니다. 검증 범위는 [릴리즈 노트](https://github.com/soom-kang/broll-me/releases/tag/v0.8.0-beta.2)를 확인하세요. 렌더링에는 [고정 버전의 로컬 실행 환경](skills/broll-me/reference/workflow.ko.md#2-입력과-팔레트-지정하기)도 필요하며, 스킬 설치만으로 준비되지는 않습니다.

### 2. 클립 요청

Codex에서 다음과 같이 요청하세요.

```text
$broll-me로 kkumil-pink 팔레트의 6초 카드를 만들어 주세요.
제목: 지난 시술 기록을 한눈에
본문: 색소 배합, 시술 사진
초안을 보여 준 뒤, 승인한 최종 MP4와 수정 가능한 장면을 전달해 주세요.
```

Claude Code에서는 `$broll-me` 대신 `/broll-me`를 사용하세요. 기존 영상에 삽입하려면 영상과 같은 영상의 SRT/VTT를 제공하고, 문구와 삽입 시간을 제안해 달라고 요청하세요. [전체 프롬프트 예시](skills/broll-me/reference/workflow.ko.md#3-프롬프트-실행하기)를 참고하세요.

### 3. 검토 후 사용

초안의 문구, 가독성, 삽입 시점을 확인한 뒤 최종 렌더링을 요청하세요. 최종 파일은 `outputs/<task>/`, 초안과 작업 파일은 `works/<task>/`에 저장합니다.

- **영상 클립:** 전체 화면 그래픽은 MP4, 투명 패널은 ProRes 4444 MOV
- **수정 가능한 원본:** 장면 HTML, 확정된 팔레트, 글꼴과 필요한 로컬 파일
- **영상 삽입 검토:** `preview.mp4`, `viewer.html`, `compare.html`, `TIMING.md`

HTML과 함께 제공된 파일은 같은 구조로 보관하세요. 옮기거나 공유하기 전에는 [결과물 안내](skills/broll-me/reference/workflow.ko.md#5-최종-파일-받기)를 확인하세요. 미리보기 파일 전달에 실패하면 재시도하기 전에 [복구 안내](skills/broll-me/reference/troubleshooting.md#media-and-delivery)를 확인하세요.

## 문서

- [설치 및 사용 가이드](skills/broll-me/reference/workflow.ko.md): 요구 환경, 입력 파일, 프롬프트, 초안 검토, 결과물
- [팔레트](skills/broll-me/reference/palettes.md): 기본 제공 6종과 사용자 지정 색상
- [CLI 사용법](skills/broll-me/reference/usage.md) · [장면 템플릿](skills/broll-me/reference/scenes.md) · [엔진 API](skills/broll-me/reference/engine-api.md)
- [적용 예시](docs/onnimm-demo.ko.md) · [핑크 카드 샘플 재현](docs/pink-demo.ko.md)
- [문제 해결](skills/broll-me/reference/troubleshooting.md)
- [기여 및 검증 안내](CONTRIBUTING.md)

## 지원 범위와 제약

HTML 기반 모션 그래픽을 만듭니다. 실사 영상 생성, 음성 인식, 원본 색 보정, 최종 마스터 편집은 지원 범위에 포함하지 않습니다.

자막에서 추정한 단어별 시점과 화자 위치는 재생하며 확인해야 합니다. 미리보기 합성은 원본 오디오 스트림을 복사하며, 지원하지 않는 시간 정보나 코덱은 오류로 알립니다. 오디오를 자동으로 변환하지 않습니다. 기술 검사를 통과해도 편집자의 최종 검토는 필요합니다.

## 라이선스

[MIT](LICENSE). 재배포할 때는 라이선스와 [글꼴·아이콘 고지](skills/broll-me/THIRD_PARTY_NOTICES.md)를 유지하세요. 작업 흐름과 에셋의 참고 출처는 [출처 안내](skills/broll-me/reference/provenance.md)에 정리되어 있습니다.
