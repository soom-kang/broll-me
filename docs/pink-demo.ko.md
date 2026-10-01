# Pink 비교 샘플 재현하기

[비교 페이지](assets/pink-demo.html)를 열고 **Play both**를 누르세요. 입력과 출력을 함께 재생하고 결과 영상의 오디오만 들려줍니다. GitHub에서는 README의 GIF를 볼 수 있습니다. HTML player는 샘플 폴더를 내려받아 로컬에서 여세요.

[English](pink-demo.md) · [한국어](pink-demo.ko.md)

## 샘플 내용

현재 broll-me로 `kkumil-pink` 팔레트의 `card`를 만들었습니다. 처음 2.436초는 화자를 보여주고, 이후 카드로 색소 배합과 시술 사진을 설명합니다. 설명용 그래픽이며 실제 제품 화면이나 고객 기록이 아닙니다.

| 항목 | 값 |
| --- | --- |
| 원본 구간 | Frame 1592~1789; 약 00:53.120~00:59.726 |
| 잘라낸 입력 | 198 frame; 6.6066초 |
| 영상 규격 | 1920×1080; `30000/1001` FPS; H.264 MP4 |
| Cutaway 구간 | 입력의 frame 73~197; 2.435767~6.6066초 |
| 그래픽 | Card template; `kkumil-pink`; 125 frame; final 렌더링 |

원본과 같은 영상의 SRT에서 문구를 가져왔습니다. 제공된 기존 전체 preview는 구간 선택에 참고했습니다. 새 결과는 `npx skills add`로 설치한 skill을 통해 렌더링했습니다. 기존 출력에서 잘라낸 결과가 아닙니다.

원본 파일은 변경하지 않았습니다. 요청한 구간을 자르고 timestamp를 0으로 맞추기 위해 샘플의 영상과 AAC 오디오를 한 번 인코딩했습니다. Preview는 이 샘플의 오디오 stream을 정규화나 변환 없이 복사했습니다. SRT cue는 구간에 맞춰 자르고 시간을 이동했으며 카드가 나올 때도 발화 자막을 표시합니다. README GIF는 무음이며 가로 1024 px, 10 FPS로 줄였습니다. 원래 샘플 FPS는 MP4에서 확인하세요.

## 샘플 재현하기

작업할 프로젝트에 broll-me를 설치하세요. 다른 프로젝트에서 재현한다면 이 checkout의 `docs/assets/`를 같은 상대 경로로 복사하세요. Codex에서는 `$broll-me`, Claude Code에서는 `/broll-me`로 시작한 뒤 아래 요청을 붙이세요.

```text
docs/assets/pink-demo-input.mp4와 docs/assets/pink-demo.srt를 읽어 주세요.
docs/assets/pink-demo-plan.json을 승인된 삽입 계획으로 사용해 주세요.
승인된 팔레트는 kkumil-pink, template은 card입니다.
처음 2.435767초는 화자를 그대로 보여 주세요.
2.435767~6.6066초에 아래 card를 넣어 주세요.
제목: 지난 시술 기록을 한눈에
부제: 설명용 그래픽
본문: 색소 배합 / 시술 사진
전체 화면 card가 나오는 동안 발화 자막도 유지해 주세요.
검사한 규격인 1920×1080, 30000/1001 FPS를 사용해 주세요.
준비된 runtime을 재사용하거나 필요한 경우 프로젝트 내부에 준비해 주세요.
draft를 보여 준 뒤 최종 clip, preview.mp4, viewer.html,
compare.html, TIMING.md, 확정된 팔레트를 motion/pink-demo/out에 저장해 주세요.
입력 파일을 변경하지 말고 preview에는 잘라낸 입력의 오디오를 복사해 주세요.
```

이 프롬프트로 내용과 삽입 계획을 재현합니다. Agent가 작성하는 배치는 달라질 수 있습니다. 제공한 배치를 그대로 만들려면 [scene JSON](assets/pink-demo-scene.json)과 [자막 포함 fragment](assets/pink-demo-card.html)를 사용하세요. Fragment는 card template을 변환한 뒤 제공된 자막과 한글 text box 보정을 추가합니다. 엔진은 변경하지 않습니다.

Skill 설치와 고정 runtime 준비를 마친 뒤 아래 명령으로 같은 장면을 렌더링하세요.

```bash
export BROLL_SKILL_DIR="$PWD/.agents/skills/broll-me"
export BROLL_RUNTIME="$PWD/motion"
python3 "$BROLL_SKILL_DIR/scripts/broll.py" doctor
python3 "$BROLL_SKILL_DIR/scripts/broll.py" build motion/pink-demo/built \
  docs/assets/pink-demo-card.html --palette kkumil-pink
python3 "$BROLL_SKILL_DIR/scripts/broll.py" check \
  motion/pink-demo/built/pink-demo-card.html
python3 "$BROLL_SKILL_DIR/scripts/broll.py" render \
  motion/pink-demo/built/pink-demo-card.html motion/pink-demo/card.mp4 \
  --fps 30000/1001 --quality final
```

검사를 통과한 HTML, shared font, 팔레트 snapshot, 125 frame card가 생성됩니다. Runtime 오류를 해결한 뒤 다시 실행하세요. Preview에는 제공된 plan을 `motion/pink-demo/plan.json`으로 복사하고, `video`를 `../../docs/assets/pink-demo-input.mp4`, clip의 `file`을 `card.mp4`로 바꾸세요. 이후 실행합니다.

```bash
python3 "$BROLL_SKILL_DIR/scripts/broll.py" preview \
  motion/pink-demo/plan.json motion/pink-demo/out/preview.mp4
```

198 frame preview와 검토 파일이 생성됩니다. 상대 경로는 plan을 기준으로 해석합니다. Timing이나 오디오 검사가 실패하면 입력을 보존하고 plan을 고치거나 승인된 호환 사본을 제공하세요.

## 파일 검토하기

1. [입력](assets/pink-demo-input.mp4)과 [출력](assets/pink-demo-output.mp4)을 재생하세요.
2. [비교 페이지](assets/pink-demo.html)와 [개별 clip viewer](assets/viewer.html)를 확인하세요.
3. [삽입 시간](assets/TIMING.md)과 [팔레트 snapshot](assets/pink-scene/palette.resolved.json)을 읽으세요.
4. [수정 가능한 scene](assets/pink-scene/pink-demo-card.html)을 옆의 font assets와 함께 여세요.
5. [기술 검증 기록](../reports/NPX_DOCUMENTATION.md)을 확인하세요. 사용자 청취와 재생 승인은 대기 상태입니다.
