# broll-me JIRA-style QA tickets

**QA-014·QA-015를 포함한 전체 누적 diff 최종 검토에서 추가로 입증된 결함이나 회귀를 찾지 못했습니다. 15건 모두 Resolved를 유지하며 새 티켓은 없습니다.** Node identity/cleanup/rename과 Build의 임시 이름 예약·첫 최종 artifact write 경계를 대조했습니다. 모든 historical 반례·resolution·생략 항목을 보존합니다.

관찰일은 2026-10-12, 최초 QA 기준 revision은 `2ba30a6cdfa84d7cc3113a5dd3948c8f7a638c18`입니다. 같은 날 QA-001부터 QA-011까지 working tree에서 수정하고 검증했습니다. 첫 누적 diff 검토에서는 QA-003·QA-010을 재개방하고 QA-012를 추가했으며, 후속 검토에서는 QA-013부터 QA-015까지 추가했습니다. 각 수정과 당시 관찰을 아래에 구분합니다. ID는 로컬 문서용이며 외부 tracker에 등록하지 않았습니다. Assignee는 **Unassigned**이며 최초 반례와 각 수정 결과를 함께 보존합니다. 로컬 ticket 해결은 실제 host 성공이나 release 승인을 뜻하지 않습니다.

Original Evidence의 source line은 위 revision을 기준으로 합니다. Final review의 line은 검토 시점 working tree를 기준으로 하며 source digest와 실행 결과는 각 review phase의 validation record에 기록합니다. 최신 전체 검토는 `post_firstwrite_final_review`, 직전 두 수정은 `qa014_qa015_follow_up`입니다. 문서만 수정한 항목은 따로 명시합니다. `[Verified]`는 직접 실행 또는 source 확인, `[Inference]`는 관찰로부터의 영향 추론입니다. Test double과 controlled interleaving는 실제 browser/process concurrency 검증과 구분합니다.

전체 판정과 검증 명령은 [QA report](QA-2026-10-12.md), 관찰 수치는 [validation record](qa-2026-10-12-validation.json)에 있습니다.

## BROLL-QA-001

**Summary:** Restore the required LICENSE in the portable Skill package
**Priority:** P1 · **Type:** Defect · **Component:** Packaging / Skill structure
**Confidence:** High · **Labels:** `release-blocker`, `portable-skill`

**Status:** Resolved — locally verified, 2026-10-12

### Current State

**Original observation:** `[Verified]` 2026-10-08 commit `2ba30a6`은 `skills/broll-me/LICENSE`를 root `LICENSE`로 이동했습니다. Validator는 package 내부 `LICENSE`를 필수로 요구하므로 최초 QA 당시 `make check`가 첫 단계에서 중단됐습니다.

최초 QA에서는 Skill의 `SKILL.md`, `THIRD_PARTY_NOTICES.md`, `reference/provenance.md`에 있는 내부 LICENSE 링크도 해결되지 않았습니다. 기존 local archive에는 해당 파일이 있으므로 과거 archive를 확인하는 것만으로 현재 source를 검증할 수 없습니다.

**Evidence:** [validator](../scripts/validate_package.py), lines 21, 88–90; [Skill](../skills/broll-me/SKILL.md), line 58; [notices](../skills/broll-me/THIRD_PARTY_NOTICES.md), line 5; [provenance](../skills/broll-me/reference/provenance.md), line 3.

### Reproduction and impact

1. Repository root에서 `python3 scripts/validate_package.py`를 실행합니다.
2. Exit `1`, `Required package files missing: LICENSE`를 확인합니다.
3. `make check`는 make exit `2`로 종료하며 이후 test command를 실행하지 않습니다.

Scratch 사본에 root LICENSE만 복원한 counterfactual은 69개 파일의 source collection, archive, extraction roundtrip을 통과했습니다. Root source와 기존 `dist/`는 변경하지 않았습니다.

### Expected State

Root LICENSE를 유지하면서 portable Skill도 필요한 MIT 문구를 자체 포함해야 합니다. 현재 source와 설치된 Skill 내부 참조가 모두 유효해야 합니다.

**Acceptance Criteria**

1. `skills/broll-me/LICENSE`에 root와 동일한 MIT notice가 포함되며 `make check`가 package 단계를 통과합니다.
2. 새 `.skill`과 `.zip`에 `broll-me/LICENSE`가 있고 exact archive/extraction 검증을 통과합니다.
3. 설치된 Skill 내부의 세 LICENSE 참조가 해결됩니다. 과거 public release는 별도 승인 없이 교체하지 않습니다.

**Original verification limit:** 최초 QA는 당시 checkout와 local historical archive만 확인했습니다. Public release 또는 fresh tagged host installation은 `NOT_RUN`이었습니다.

### Resolution

Root LICENSE를 그대로 두고 `skills/broll-me/LICENSE`에 동일한 bytes를 복원했습니다. `make check PYTHON=.runtime/motion/.venv/bin/python`은 package 69 files, Python 69 tests, Node 18 tests를 모두 통과했습니다. 현재 source를 `/private/tmp`의 `.skill`과 `.zip`으로 packaging하고 exact bytes/extraction, 내부 LICENSE 참조를 확인했습니다. 두 archive의 LICENSE는 root와 같습니다.

기존 `dist/`와 public release는 교체하지 않았습니다. 새 tagged host installation과 release는 `NOT_RUN`입니다. 검증 당시 source digest는 [P1 follow-up record](qa-2026-10-12-validation.json)의 `p1_follow_up`에서 확인할 수 있습니다.

## BROLL-QA-002

**Summary:** Protect build inputs against hard-link output aliases
**Priority:** P1 · **Type:** Defect · **Component:** Scene build / file preservation
**Confidence:** High · **Labels:** `input-integrity`, `filesystem`

**Status:** Resolved — locally verified, 2026-10-12

### Current State

**Original observation:** `[Verified]` 최초 QA 당시 `preflight_outputs()`는 resolved path만 비교했습니다. Output이 input의 hard link이면 path가 달라 검사를 통과했고, `destination.write_text()`가 같은 inode를 직접 수정해 원본 fragment를 compiled HTML로 바꿨습니다. 기존 output symlink도 연결 대상에 쓰기를 수행했습니다.

**Evidence:** [build.py](../skills/broll-me/engine/build.py), lines 25–38, 72–75; [input preservation contract](../skills/broll-me/SKILL.md), line 25.

### Reproduction and impact

1. `/private/tmp`에 fragment 사본과 output path를 준비합니다.
2. `os.link(source, destination)`으로 같은 inode를 연결한 뒤 `build(source, destination, font_mode='embedded')`를 호출합니다.
3. `source.read_bytes()`가 변경되고 compiled HTML이 된 것을 확인합니다.

실제 filesystem에서 `source_overwritten=True`를 관찰했습니다. Input과 무관한 파일에 연결된 output symlink도 target을 덮어썼습니다. 기존 task를 이어 하거나 explicit output 폴더를 재사용할 때 발생할 수 있으며 race가 필요하지 않습니다.

### Expected State

Input과 output의 alias 여부를 실제 파일 identity까지 확인하고, 실패 또는 publication 과정에서 보호한 입력 bytes를 유지해야 합니다.

**Acceptance Criteria**

1. 기존 output이 보호된 input과 같은 inode이면 첫 write 전에 거부하며 입력 hash가 그대로입니다.
2. Output symlink 정책을 명시하고 기본 경로에서 target에 의도하지 않은 write를 하지 않습니다.
3. HTML을 임시 파일에서 준비해 publication하며, 거부된 alias 사례에 path와 recovery action을 출력합니다.

**Original verification limit:** 최초 QA는 실제 local hard link/symlink만 검증했습니다. Concurrent alias 교체와 OS 권한 공격은 `NOT_RUN`이었습니다. 새 task 폴더 사용은 노출을 줄이지만 당시 검사 결함 자체를 고치지는 않았습니다.

### Resolution

`check_destination()`이 resolved path와 `Path.samefile()`을 함께 검사하고 HTML output symlink를 거부합니다. CLI는 기존 batch preflight에서 전체 source와 custom palette를 보호합니다. HTML은 같은 directory의 임시 파일에서 작성·flush한 뒤 `os.replace()`로 lexical output entry를 교체합니다. 임시 파일은 정상 종료와 예외 경로에서 정리합니다.

기존 `tests/test_palette.py`에 4개 regression test를 추가했습니다. Fragment, SceneSpec, custom palette의 hard link를 첫 write 전에 거부했고, batch의 이후 source에 연결된 output과 무관한 파일로 향하는 symlink도 원본 bytes를 보존했습니다. Publication 직전 alias를 삽입한 controlled interleaving에서는 source가 보존되고 output은 독립된 inode가 됐습니다. 기존 정상 build 사례와 함께 통과했습니다.

실제 multiprocess/parent-directory 교체 공격은 `NOT_RUN`입니다. 이 P1 수정 당시 HTML/palette publication과 direct media output symlink 정책은 QA-004/003의 후속 범위였습니다. 현재 판정은 각 ticket과 최종 review에 기록합니다.

## BROLL-QA-003

**Summary:** Preflight known output and font conflicts before direct publication
**Priority:** P2 · **Type:** Safety risk · **Component:** Media publication
**Confidence:** High for observed behavior · **Status:** Resolved — complete preflight locally verified, 2026-10-12
**Labels:** `filesystem`, `output-policy`

### Current State

**Cumulative re-review observation:** `[Verified]` Fixed/derived symlink 검사는 유지되지만 non-regular output과 shared-font destination의 알려진 충돌은 첫 mutation 전에 검사하지 않습니다. 아래 다섯 반례에서 이전 page/panel/contact가 교체된 뒤 실패했습니다.

**Reopened observation:** `[Verified]` Direct caller가 첫 destination만 사전 검사합니다. 뒤쪽 output symlink 거부 전에 앞선 정상 output이 교체되므로 아래 원래 symlink 수정만으로 failure preservation은 충족하지 못합니다.

**Original observation:** `[Verified]` 최초 QA 당시 `atomic_output()`는 lexical output path를 검사하기 전에 `resolve()`했습니다. 기존 symlink의 target이 protected input 목록에 없으면 target에 임시 파일을 publish하고 symlink를 남겼습니다. 반면 `publish_bundle()`은 output symlink를 거부했습니다.

**Evidence:** [media.py](../skills/broll-me/scripts/media.py), lines 166–180; [preview_bundle.py](../skills/broll-me/scripts/preview_bundle.py), lines 25–27.

### Reproduction and impact

1. 임시 directory에서 `output.symlink_to(target)`를 만듭니다.
2. `with atomic_output(output, suffix='.mp4') as temporary:` 안에서 새 bytes를 씁니다.
3. Symlink는 그대로이며 `target`의 이전 bytes가 교체됩니다.

실제 helper를 실행해 재현했습니다. Direct composite/page entry point의 output은 preview bundle보다 약한 alias 정책을 적용합니다. 선택한 output directory 밖의 target도 교체될 수 있습니다. 이것을 remote exploit이나 protected-input bypass로 표현하지 않습니다.

### Expected State

Direct output과 preview bundle이 동일하고 문서화된 symlink 계약을 적용해야 합니다. 알려진 destination type과 shared-font 거부 조건도 첫 output mutation 전에 검사해 이전 결과를 보존해야 합니다. 최초 QA에서 제기한 symlink 지원 결정은 기본 거부로 정해졌습니다.

**Acceptance Criteria**

1. Alias resolution 전에 lexical output path와 관련 parent의 symlink를 검사합니다.
2. 거부 시 symlink와 target bytes를 모두 보존하며 direct/bundle 동작이 일치합니다.
3. 의도적인 symlink output을 지원하기로 결정하면 explicit opt-in, 범위, 경고와 recovery 동작을 문서화합니다.
4. Direct pages의 viewer/compare/TIMING 및 panel preview, inspection의 contact/report 등 전체 destination을 첫 write 전에 검사합니다. 알려진 alias 거부 시 이전 정상 output과 assets를 변경하지 않습니다.
5. 이 destination의 non-regular type과 shared-font target의 symlink/type/differing-bytes 거부 조건을 panel rendering, font copy와 page/contact publication 전에 검사합니다. 알려진 충돌이 있으면 기존 outputs/inputs/assets를 보존하고 encoder 호출도 시작하지 않습니다. 정상 재사용과 late publication 재검사는 유지합니다.

**Original verification limit:** 실제 filesystem publication은 확인했으나 FFmpeg는 이 사례에 필요하지 않았습니다. Symlink 지원 의도는 당시 `[Unverified]`였습니다.

### Resolution

기본 정책을 output symlink 거부로 통일했습니다. `atomic_output()`은 lexical destination과 parent를 resolve 전에 검사하고 publication 직전에 재검사합니다. 임시 파일 cleanup은 원래 output directory의 file descriptor에 고정해 parent가 symlink로 바뀌어도 다른 directory의 같은 이름 파일을 삭제하지 않습니다. 표준 macOS `/tmp`·`/var` alias만 그대로 지원합니다.

`inspect_video`, `make_pages`, `preview_bundle`도 선택한 output directory의 alias를 지우기 전에 같은 검사를 적용합니다. 읽을 수 있는 input symlink는 허용하며, direct review pages는 선택한 preview argument 옆에 생성합니다. Preview-file symlink의 target directory로 output을 옮기지 않습니다.

기존 delivery suite에 7개 regression test를 추가해 정상 교체, final/dangling/parent symlink, controlled late alias, caller의 alias 거부와 readable preview symlink를 확인했습니다. Link, target와 이전 정상 output bytes를 보존했습니다. 마지막 검사와 replace 사이의 hostile multiprocess race는 `NOT_RUN`이며 완전한 race 방어로 보고하지 않습니다.

### Final review — Reopened, 2026-10-12

[make_pages.py](../skills/broll-me/scripts/make_pages.py), lines 47–48은 viewer만 preflight합니다. Lines 69–78/97–99에서 panel preview, fonts와 앞선 page를 쓴 뒤 compare 또는 TIMING의 alias를 거부합니다. [inspect_video.py](../skills/broll-me/scripts/inspect_video.py), line 63도 contact만 검사해 report의 alias 거부(line 78) 전에 contact를 교체합니다.

실제 filesystem에서 기존 승인 page bytes와 뒤쪽 symlink를 두고 direct `write_pages()`를 호출했습니다. Compare symlink에서는 viewer가 교체됐고 TIMING symlink에서는 viewer와 compare가 교체됐습니다. 두 경우 shared font assets도 생성됐습니다. Inspection의 video.json symlink에서도 contact.png가 교체됐습니다. Links, targets와 source는 보존됐습니다. Metadata, encoder와 NumPy 분석만 controlled doubles이며 실제 publication 함수를 사용했습니다.

**Required correction:** 전체 fixed/derived destination을 mutation 전에 검사하고 기존 atomic publication 재검사도 유지합니다. 전체 transaction이나 hostile race 방어를 새로 도입하지 않습니다. 기존 delivery suite에 뒤쪽 alias와 panel-preview alias의 bounded regression을 보완합니다.

**Verification boundary:** 세 반례 결과는 `final_diff_review`에 포함합니다. Actual FFmpeg 실행·hostile directory concurrency는 이 counterexample에서 필요하지 않아 `NOT_RUN`입니다. 이번 review에서 implementation은 수정하지 않았습니다.

### Follow-up resolution — 2026-10-12

Fixed viewer/compare/TIMING destinations와 모든 derived panel-preview 경로를 mutation 전에 검사합니다. Known input-path 충돌도 같은 단계에서 거부하며 계산한 panel path를 rendering에 재사용합니다. Inspection은 contact.png와 video.json 모두 probe/encoder/write 전에 검사합니다. 기존 atomic publication 재검사, readable input/preview symlinks와 macOS temp alias는 유지합니다. 공유 helper나 transaction framework는 추가하지 않았습니다.

기존 delivery suite의 4개 regression에서 compare/TIMING의 existing/dangling link, 두 번째 panel preview link와 inspection report link를 거부할 때 이전 pages/panel/contact/font와 target/source bytes를 보존했습니다. Renderer와 font-copy 호출은 발생하지 않았으며 정상 panel/shared-font pages 생성도 통과했습니다. Focused delivery 39 tests와 전체 Python 94/Node 25, package 69 files를 통과했습니다.

**Verification limit:** 실제 filesystem/font copy이며 metadata/encoder는 controlled doubles입니다. 새로운 전체 bundle transaction, arbitrary filesystem failure rollback와 hostile multiprocess race를 보장하지 않습니다. 상세 결과는 `final_review_corrections`에 기록합니다.

### Cumulative re-review — Reopened, 2026-10-12

[make_pages.py](../skills/broll-me/scripts/make_pages.py), lines 63–66의 preflight는 path의 symlink/input 충돌만 검사합니다. Destination이 directory이면 첫 write 전에 알 수 있지만 뒤쪽 publication에서야 실패합니다. Shared-font 검사는 line 89의 `local_fonts()`에서 수행하며 panel preview는 lines 82–84에서 이미 publish합니다. [inspect_video.py](../skills/broll-me/scripts/inspect_video.py), lines 63–67도 report type을 검사하지 않습니다.

실제 filesystem의 다섯 반례를 확인했습니다. Compare directory는 이전 viewer를, TIMING directory는 viewer/compare를 교체한 뒤 실패했으며 font 5개도 생성됐습니다. Shared-font symlink 또는 differing file은 이전 panel preview를 교체한 뒤 ValueError를 반환했습니다. Inspection report directory는 contact sheet 교체 후 IsADirectoryError가 발생했습니다. Inputs, blocked directories와 font asset/target bytes는 보존됐습니다.

**Expected correction:** Known page/panel/inspection destination의 symlink/input/type 검사와 공유 font destination의 alias/type/bytes validation을 첫 mutation 전에 완료합니다. 기존 atomic checks를 유지하고 기존 delivery suite에서 이전 output 보존과 encoder/font-copy 미호출을 확인합니다. Shared font validation만 앞당긴다고 먼저 assets를 쓰는 다른 partial state를 만들지 않아야 합니다. 여러 파일의 transaction/전체 rollback이나 hostile race 방어는 별도 요구하지 않습니다.

**Evidence:** `cumulative_re_review`의 five filesystem counterexamples와 source locations. 실행: `.runtime/motion/.venv/bin/python /private/tmp/broll-rereview-safety-oeo2urak/probe.py`. Metadata/encoder만 controlled doubles이며 기존 publication/font helpers와 inspection NumPy 분석을 사용했습니다. 실제 FFmpeg execution와 hostile concurrency는 해당 반례에서 `NOT_RUN`입니다. 이번 재검토에서 source/tests는 수정하지 않았습니다.

### Complete preflight resolution — 2026-10-12

`validate_output_path()`는 final symlink/non-regular type과 parent symlink/non-directory type을 mutation 없이 검사합니다. Direct pages의 모든 fixed/derived 경로와 inspection의 contact/report가 이 검사를 먼저 통과해야 하며 `atomic_output()`도 실제 publication 직전 재검사합니다. Non-regular destination과 file인 parent는 content를 읽거나 교체하지 않고 거부합니다.

`validate_shared_fonts()`는 기존 complete-set source/notice/path/type/byte 검사를 copy와 분리합니다. Shared mode의 direct caller는 panel encoder 전에 이를 실행하고, 기존 `shared_fonts()`는 mkdir/copy 직전 같은 검사를 반복합니다. Validation은 폴더나 assets를 만들지 않습니다. Font source와 named OFL text, 동일 asset 재사용/Path return, macOS `/tmp`·`/var`, readable input alias를 유지합니다. Embedded mode는 관련 없는 shared output assets를 검사하지 않습니다.

기존 delivery suite에 6개 regression method를 추가했습니다. 17 failure subcases에서 encoder/font-copy 미호출과 filesystem 전체 보존을 확인했고 정상 reused fonts/panel/page와 embedded mode도 통과했습니다. Focused delivery 45, 전체 Python 100/Node 25, package 69 files를 통과했습니다. 이전 다섯 counterexample도 encoder calls 0, changed outputs 0으로 거부됐습니다.

별도 reviewer의 matrix 14개와 실제 CLI FFmpeg inspection, 정상 shared-font pages 생성을 확인했습니다. Unix socket 생성은 sandbox `Operation not permitted`로 실제 사례를 실행하지 못했습니다. `NOT_RUN`이며 다른 non-regular type 사례로 대체해 socket 성공을 주장하지 않습니다.

**Verification limit:** Known rejection preflight와 late checks이며 multi-file transaction이나 hostile race/OS-exit recovery의 새 보장은 아닙니다. 상세 command, source digest, five-counterexample results와 보존 확인은 `qa003_complete_preflight_follow_up`에 있습니다. 실제 host/editor approval와 release는 `NOT_RUN`입니다.

## BROLL-QA-004

**Summary:** Preserve prior build artifacts when palette publication fails
**Priority:** P2 · **Type:** Defect · **Component:** Build consistency / recovery
**Confidence:** High for controlled failure · **Labels:** `publication`, `recovery`

**Status:** Resolved — locally verified, 2026-10-12

### Current State

**Original observation:** `[Verified]` 최초 QA 당시 build는 palette preflight 이후 HTML을 덮어쓰고 마지막에 snapshot을 썼습니다. 그 사이 다른 writer가 다른 palette snapshot을 publish하면 snapshot 검증은 실패했지만 이미 교체한 HTML을 되돌리지 않았습니다. 기존 승인 output이 사라지고 HTML과 snapshot의 palette가 달라졌습니다.

**Evidence:** [build.py](../skills/broll-me/engine/build.py), lines 48, 60, 73–75; [failure preservation contract](../skills/broll-me/SKILL.md), line 46; [CLI delivery contract](../skills/broll-me/reference/usage.md), line 40.

### Reproduction and impact

1. Destination에 이전 승인 output을 두고 warm-orange build를 준비합니다.
2. `font_css()` 호출 시점에 controlled callback으로 midnight-cyan snapshot을 publish합니다.
3. `write_snapshot()`은 `PaletteError`로 실패하지만 `prior_output_preserved=False`, HTML은 warm-orange, snapshot은 midnight-cyan으로 남습니다.

실제 함수와 filesystem을 사용했습니다. Callback은 다른 writer publication의 순서만 제어했으며 multiprocess race 빈도를 측정한 것은 아닙니다.

### Expected State

Single build가 실패하면 이전 HTML과 snapshot을 보존하거나 복구 가능한 상태를 명확하게 남겨야 합니다. 서로 충돌하는 palette bundle을 완료 output으로 취급하지 않아야 합니다.

**Acceptance Criteria**

1. Conflicting publication 반례에서 기존 승인 HTML을 보존하고 mismatched 새 HTML을 publish하지 않습니다.
2. Publication 직전에 compatibility를 확인하고 writer coordination 또는 rollback을 적용합니다.
3. 복구가 실패하면 partial state와 recovery 위치를 출력합니다. 같은 directory를 재사용하는 정상 build는 유지합니다.

**Original verification limit:** Deterministic interleaving만 실행했습니다. 실제 multiprocess race, disk-full, sudden OS exit는 당시 `NOT_RUN`이었습니다.

### Resolution

HTML을 stage에 준비한 뒤 build와 standalone palette writer가 공유하는 `.broll-palette.lock` 안에서 output/snapshot을 다시 검사합니다. Snapshot을 먼저 create-if-absent로 publish하고 HTML을 교체합니다. HTML publication이 실패하면 이번 build가 생성한 snapshot만 inode identity 확인 후 되돌립니다. 기존 compatible snapshot과 승인 HTML은 보존합니다. API에서도 예약 snapshot 이름을 HTML destination으로 사용할 수 없습니다.

Rollback이나 cleanup이 실패하면 `PaletteRecoveryError`가 상태와 recovery 위치를 보고합니다. Snapshot rollback 또는 palette writer cleanup 실패는 필요한 stage와 lock을 보존해 writer를 차단하며 자동으로 stale lock을 회수하지 않습니다. 최종 HTML stage cleanup 실패는 publication 상태와 stage 위치를 보고하지만 lock이 이미 해제됐을 수 있습니다. 이 경로도 파일을 수동 확인한 후 재시도해야 합니다. Cleanup 오류는 일관된 output이 이미 publish된 뒤 발생할 수도 있습니다.

기존 palette suite에 3개 regression test와 예약 이름 충돌 subcase를 추가했습니다. 원래 controlled palette 충돌, 새 snapshot rollback, 기존 snapshot bytes/mtime 보존, rollback 실패의 recovery 보존과 retry 차단을 확인했습니다. 실제 두 child writer도 보유 중인 lock에서 거부됐으며 lock 해제 후 정상 build가 완료됐습니다. 이는 cooperating writer coordination이며 두 파일의 atomic visibility, 전체 batch transaction이나 sudden OS exit recovery를 증명하지 않습니다.

## BROLL-QA-005

**Summary:** Accumulate transparent motion blur with correct alpha semantics
**Priority:** P2 · **Type:** Defect · **Component:** Final alpha rendering
**Confidence:** High · **Labels:** `alpha`, `motion-blur`, `visual-quality`
**Status:** Resolved — locally verified, 2026-10-12

### Current State

**Original observation:** `[Verified]` 최초 final filter의 `format=gbrap,tmix`는 RGB와 alpha를 각각 평균냈습니다. Opaque white 1개와 transparent black 3개를 평균내면 `[64,64,64,64]`가 됐습니다. Straight alpha로 합성할 때 색 밝기가 다시 alpha로 감쇠해 dark edge가 생겼습니다. Draft에는 `tmix`가 없어 final과 결과가 달랐습니다.

**Evidence:** [render.js](../skills/broll-me/engine/render.js), lines 40–46.

### Reproduction and impact

2×2 RGBA rawvideo 4 frames를 준비합니다. 첫 frame은 `[255,255,255,255]`, 나머지는 `[0,0,0,0]`입니다. 아래 실제 final filter와 `prores_ks`, profile `4`, `yuva444p10le`를 사용해 MOV를 만든 뒤 RGBA로 decode했습니다.

```text
format=gbrap,tmix=frames=4:weights='1 1 1 1',select='eq(mod(n\,4)\,3)',setpts=N/(30/1)/TB
```

FFmpeg `9.0.2` 결과는 `[64,64,64,64]`였습니다. Quarter coverage의 white straight-alpha 값은 `[255,255,255,64]`여야 합니다. 검정 배경 합성 밝기가 약 `16`으로 줄어드는 반면 올바른 coverage 밝기는 약 `64`입니다. 움직이는 transparent panel의 경계에 영향을 줍니다.

다음은 실행한 codec counterexample입니다. 생성 파일은 자동 정리되는 임시 directory에만 기록합니다.

```bash
python3 - <<'PY'
from pathlib import Path
import subprocess, tempfile
with tempfile.TemporaryDirectory(prefix='broll-qa-alpha-', dir='/private/tmp') as d:
    raw, output = Path(d)/'input.rgba', Path(d)/'actual.mov'
    raw.write_bytes(bytes([255,255,255,255])*4 + bytes([0,0,0,0])*12)
    vf = "format=gbrap,tmix=frames=4:weights='1 1 1 1'," \
         "select='eq(mod(n\\,4)\\,3)',setpts=N/(30/1)/TB"
    subprocess.run(['ffmpeg','-v','error','-f','rawvideo','-pixel_format','rgba',
        '-video_size','2x2','-framerate','120','-i',str(raw),'-vf',vf,'-r','30/1',
        '-c:v','prores_ks','-profile:v','4','-pix_fmt','yuva444p10le','-vendor','apl0',
        str(output)],capture_output=True,check=True)
    decoded = subprocess.run(['ffmpeg','-v','error','-i',str(output),'-pix_fmt','rgba',
        '-frames:v','1','-f','rawvideo','-'],capture_output=True,check=True)
    print(list(decoded.stdout[:4]))
PY
```

### Expected State

Premultiplied alpha로 누적한 후 output 계약에 맞게 변환하거나, 같은 색·coverage 결과를 보존하는 동등한 방식으로 처리해야 합니다.

**Acceptance Criteria**

1. 위 white/transparent 반례를 filter와 MOV decode 모두에서 허용 codec 오차 내 `[255,255,255,64]`로 처리합니다.
2. 검정 배경 합성에서 quarter coverage 밝기를 유지하고 완전 transparent pixel에 NaN이나 색 오염이 없습니다.
3. Opaque MP4, rational FPS, frame count와 ProRes alpha output 계약을 유지합니다.

**Original verification limit:** Browser screenshot input은 controlled RGBA로 대체했습니다. Filter, encoder, decoder는 실제 실행했습니다.

### Resolution — 2026-10-12

Final alpha filter는 `gbrap16le`에서 RGB를 premultiply하고 4개 subframe을 평균 낸 뒤 선택한 frame을 unpremultiply합니다. 실제 FFmpeg filter와 ProRes decode에서 quarter-white는 `[255,255,255,64]`, 완전 transparent는 `[0,0,0,0]`입니다. Low alpha, mixed color와 opaque 입력도 channel별 허용 오차 `2` 이내에서 확인했습니다.

실제 Chromium PNG가 RGB24/RGBA 사이를 전환하면 FFmpeg의 기본 reinitialization이 `tmix`와 `select` 상태를 초기화하는 추가 반례가 나왔습니다. Alpha final에만 input option `-reinit_filter 0`을 적용했습니다. 고정 viewport의 RGB→RGBA, 역방향과 반복 전환에서 12 captures가 3 output frames로 유지됐습니다. Production filter·input options를 사용하는 기존 Node test에 codec regression을 추가했습니다.

실제 Chromium에서 64×64, 0.1초 scene을 final로 렌더링했습니다. MOV decode는 3 frames, `30/1`, ProRes alpha이며 첫 pixel `[255,255,255,128]`, 다음 frame `[0,0,0,0]`입니다. Opaque MP4도 3 frames를 유지합니다. Controlled PNG/ProRes regression은 `30000/1001`에서 frame 수와 coverage를 확인합니다. Draft와 opaque filter는 변경하지 않았습니다.

**Verification limit:** Pinned FFmpeg `9.0.2`와 Chromium `151.0.7922.34`, 고정 viewport 및 synthetic scene의 근거입니다. 다른 runtime 버전, 전체 scene의 편집자 시각 승인과 실제 host 평가는 `NOT_RUN`입니다.

## BROLL-QA-006

**Summary:** Let renderer cleanup complete before terminating a timed-out child
**Priority:** P2 · **Type:** Defect · **Component:** CLI cancellation / resource lifecycle
**Confidence:** High for cleanup skip · **Labels:** `timeout`, `observability`
**Status:** Resolved — locally verified, 2026-10-12

### Current State

**Original observation:** `[Verified]` Parent의 `subprocess.run(..., timeout=...)` deadline이 renderer 내부보다 먼저 시작됐습니다. Parent가 Node를 종료하면 `render()`의 `finally`가 실행되지 않아 `.broll-render-*`가 남았습니다. Exit `124`는 cleanup 완료를 뜻하지 않습니다.

**Evidence:** [broll.py](../skills/broll-me/scripts/broll.py), lines 39–47; [render.js](../skills/broll-me/engine/render.js), lines 63–66; [runtime.js](../skills/broll-me/engine/runtime.js), lines 91–105.

### Reproduction and impact

1. 실제 `broll.execute()` 함수를 import하여 Node driver를 실행하고 `BROLL_TIMEOUT_MS=1000`을 설정합니다.
2. Driver는 actual `render()`와 FFmpeg를 사용합니다. Browser는 screenshot 100ms 지연과 close marker를 기록하는 stub이며 scene은 2초, 30 FPS draft입니다.
3. Exit `124`, `node timed out after 1s`, render 임시 directory 잔존, close marker 부재, final output 부재를 확인했습니다.

`[Inference]` 반복 timeout은 큰 intermediate 파일을 누적시킬 수 있습니다. 실제 Chromium orphan이 계속 남는다는 주장은 검증하지 않았습니다.

### Expected State

Timeout 책임을 한 경계에서 관리하거나, bounded graceful cancellation을 먼저 요청한 후 필요한 경우 강제 종료해야 합니다. 종료와 cleanup 결과를 별도로 진단할 수 있어야 합니다.

**Acceptance Criteria**

1. 같은 반례에서 renderer가 cleanup 기회를 받고 임시 directory가 남지 않습니다. 강제 종료가 필요하면 미정리 artifact 위치를 명시합니다.
2. Final exit `124`를 유지하고 기존 input/output bytes를 보존합니다.
3. 실제 Chromium/FFmpeg child 종료도 별도 확인하며, cleanup 실패를 성공 또는 완료로 표시하지 않습니다.

**Original verification limit:** 실제 `broll.execute()` 함수, renderer와 FFmpeg를 사용했지만 browser는 stub입니다. CLI argument dispatch와 실제 Chromium descendant persistence는 이 반례에서 `NOT_RUN`이었습니다.

### Resolution — 2026-10-12

CLI는 child를 POSIX에서 독립 process group으로 시작하고 deadline에 `SIGTERM`을 보냅니다. Cleanup grace는 5초이며 이후 남은 owned group에 `SIGKILL`을 보냅니다. Diagnostic capture와 reap에도 각 1초의 제한을 두었습니다. Exit `124`와 stdout의 단일 error JSON을 유지하고 stderr에 cleanup 완료·실패·강제 종료를 구분해 기록합니다.

Renderer는 `AbortController`로 capture/encoding 대기를 중단하고 encoder와 browser cleanup을 각각 시도합니다. Scene을 여는 도중 cancellation도 acquired browser를 닫습니다. Resource cleanup이 성공한 뒤 video를 publish하므로 cleanup 중 취소하면 기존 output을 보존합니다. Cleanup 실패는 완료로 표시하지 않으며 staging 경로를 보고합니다.

실제 CLI dispatch, Chromium, FFmpeg로 `BROLL_TIMEOUT_MS=3000`의 stalled `seek()`를 확인했습니다. 약 `3.113`초 후 exit `124`와 `cancellation cleanup completed`를 받았고, 관찰한 Node·Chromium 4개·FFmpeg PID가 모두 종료됐습니다. `.broll-render-*`는 없고 input과 이전 output hash가 동일합니다. Browser가 별도 group에서 실행된 이 정상 cancellation 사례에서도 close가 완료됐습니다.

기존 Python suite의 5개 regression은 정상 exit, invalid timeout, cooperative signal, inherited pipe를 유지하는 stubborn descendant의 bounded force와 JSON `124`를 확인합니다. Node regression 2개는 capture/cleanup 중 cancellation, cleanup 오류에서도 다른 resource 정리, 기존 output·signal listener 보존을 확인합니다.

**Verification limit:** Force는 JavaScript cleanup을 실행하지 못합니다. Owned group에서 이탈한 descendant, non-POSIX host, OS crash와 모든 shutdown race의 cleanup은 보장하지 않습니다. 이 경우 diagnostics와 남은 staging을 확인해야 하며 완료로 보고하지 않습니다. 실제 host/provider 평가와 human playback은 `NOT_RUN`입니다.

## BROLL-QA-007

**Summary:** Include readable font notices in embedded HTML exports
**Priority:** P2 · **Type:** Defect · **Component:** Portable delivery / documentation
**Confidence:** High · **Labels:** `embedded-export`, `font-notices`
**Status:** Resolved — locally verified, 2026-10-12

### Current State

**Original observation:** `[Verified]` Baseline의 두 workflow 문서는 shared/embedded 모두 font notices를 유지한다고 설명했습니다. 당시 `font_css()`는 shared mode에서만 notices를 복사하고 embedded mode에서는 font bytes만 data URL로 넣었습니다. 실제 embedded build output은 HTML과 palette snapshot뿐이며 두 full OFL text가 없었습니다.

Shared mode는 `OFL-Geist.txt`와 `OFL-NotoSansKR.txt`를 정상 복사합니다. 확인한 Noto TTF 내부 license field도 OFL 설명과 URL이며 full notice 전문이 아닙니다.

**Original documentation status:** 최초 QA에서는 paired workflow 문서에 누락과 notice 동반 전달 방법만 정정했습니다. 당시 export 구현은 미수정이었으며 ticket은 open이었습니다.

**Evidence:** [fonts.py](../skills/broll-me/engine/fonts.py), lines 43–58; baseline [workflow.md](../skills/broll-me/reference/workflow.md) / [workflow.ko.md](../skills/broll-me/reference/workflow.ko.md), line 123.

### Reproduction and impact

```bash
python3 skills/broll-me/engine/build.py /private/tmp/broll-notice-example \
  --scene skills/broll-me/examples/scenes/card.json --font-mode embedded
```

Fresh scratch directory에서 HTML의 3개 data font와 notice 전문/sidecar 부재를 확인했습니다. 문서대로 HTML만 공유하면 약속한 notice bundle이 전달되지 않습니다. 법적 적합성 판정은 수행하지 않았습니다.

### Expected State

Embedded HTML export가 font 데이터와 원래 notices의 읽을 수 있는 전문을 함께 포함해야 합니다. 참조하는 media와 custom assets의 별도 전달 조건은 유지합니다.

**Acceptance Criteria**

1. Embedded HTML 자체에 두 font notices의 copyright와 full license text를 포함하며 외부 URL만으로 대신하지 않습니다.
2. Shared mode는 기존 notice 파일을 유지하며 required notice가 없으면 export를 성공으로 보고하지 않습니다.
3. 두 언어의 사용 가이드와 생성 결과가 일치합니다. Notices 추가가 visual scene framing을 바꾸지 않습니다.

**Original verification limit:** Artifact inspection과 원본 font metadata 일부를 확인했습니다.

### Resolution — 2026-10-12

Embedded `font_css()`에 `OFL-Geist.txt`와 `OFL-NotoSansKR.txt`의 copyright 및 전문을 이름이 붙은 CSS 주석으로 포함합니다. `<style>` 또는 CSS 주석을 닫을 수 있는 문자는 가역적으로 인코딩하며 원문을 복원할 수 있습니다. 별도 DOM 요소나 visible UI는 추가하지 않았습니다. 두 mode 모두 필수 원본 notice가 누락되거나 비어 있으면 export를 거부합니다.

실제 CLI로 만든 embedded scene HTML과 `make_pages.py`로 만든 viewer/compare HTML에서 두 전문을 원본과 대조했습니다. Shared는 기존 font 3개와 notice 2개의 bytes, 재사용과 충돌 시 보존 동작을 유지합니다. 실제 build의 missing-notice 실패에서 기존 HTML bytes와 directory entries도 보존됐습니다.

Chromium에서 640×360 scene의 `seek(0.5)`를 확인했습니다. Notice 포함본, notice 주석만 제거한 비교본과 shared HTML의 screenshot SHA-256이 동일합니다. 세 font를 실제 weight `500`으로 로딩했으며 scene과 review page의 resource/page 오류는 없었습니다. 기존 delivery suite에 full notices, missing/empty와 HTML/CSS escape 회귀 검사 3개를 추가했습니다. OFL 원문 URL이 기존 offline 검사에 잡혀 named notice 주석만 제외하도록 해당 assertion을 갱신했습니다.

Paired workflow, usage, troubleshooting와 third-party notices를 실제 export 계약으로 갱신했습니다. 참조하는 media/custom assets의 별도 전달 조건은 유지합니다.

**Verification limit:** Synthetic scene의 특정 시점과 review page font loading을 확인했습니다. 전체 font compliance, 법률 검토, 실제 host/provider 평가와 편집자의 전체 playback 승인은 `NOT_RUN`입니다.

## BROLL-QA-008

**Summary:** Reject malformed portable YAML before approving a package
**Priority:** P2 · **Type:** Defect · **Component:** Package validation
**Confidence:** High · **Labels:** `frontmatter`, `validation-boundary`
**Status:** Resolved — locally verified, 2026-10-12

### Current State

**Original observation:** `[Verified]` Linewise regex validator는 닫히지 않은 single quote를 거부하지 않았습니다. `metadata`가 이전에 한 번 등장하면 뒤에 다른 scalar가 있어도 indented mapping을 허용했습니다. 실제 YAML parser는 같은 두 입력을 syntax error로 거부했습니다. Stdlib packager는 malformed fixture archive를 생성하고 검증 성공 manifest를 썼습니다.

**Evidence:** [validate_package.py](../scripts/validate_package.py), lines 26–46; [package.py](../scripts/package.py), lines 62–66.

### Reproduction and impact

```yaml
---
name: broll-me
description: 'Build branded B-roll
license: MIT
---
```

`validate_frontmatter()`는 통과하지만 Ruby `YAML.safe_load`는 `Psych::SyntaxError`를 반환합니다. 별도 사례 `metadata: {}` 뒤에 `description: Build B-roll`과 indented `host_only: invalid nested scalar`를 두어도 같은 차이가 발생했습니다. 첫 malformed fixture는 8 files의 stdlib package로 성공했습니다.

현재 canonical `SKILL.md`의 YAML이 잘못됐다는 의미는 아닙니다. Package 단계가 잘못된 입력을 놓쳐 host loading까지 오류 발견이 늦어질 수 있는 validator 결함입니다.

### Expected State

Portable subset을 유지하더라도 quoted scalar와 실제 metadata nesting의 syntax를 검증해야 합니다. Creator backend 유무가 적합성 판정을 바꾸지 않아야 합니다.

**Acceptance Criteria**

1. 두 counterexample을 거부하고 invalid archive/manifest를 성공으로 생성하지 않습니다.
2. 정상 canonical frontmatter와 유효한 metadata map은 계속 통과합니다.
3. Stdlib fallback과 creator backend의 portable frontmatter verdict가 일치합니다. 새 production dependency는 승인 없이 추가하지 않습니다.

**Original verification limit:** Regex validator, Ruby parser와 stdlib packaging을 실제 실행했습니다. Actual Codex/Claude malformed-Skill loading은 `NOT_RUN`이었습니다.

### Resolution — 2026-10-12

Stdlib validator가 지원하는 portable subset을 명시하고 syntax와 field type을 검사합니다. `name`, `description`, `license`는 single-line string이며 `metadata`는 `{}` 또는 정확히 두 space로 들여쓴 flat map입니다. Plain string, JSON double quote와 YAML single quote를 지원합니다. Metadata의 단순 scalar는 문자열, JSON 형식 숫자, boolean과 null을 허용합니다. Lists, nested maps, multiline values, tags, anchors와 `{}` 이외의 flow map은 거부합니다.

닫히지 않은 quote, quoted scalar 뒤 garbage, duplicate key, 잘못된 colon delimiter와 active metadata 이외의 nesting을 거부합니다. 추가 검토에서 Unicode whitespace가 quote 뒤를 잘못 정리하는 반례를 확인해 syntax trim을 ASCII space로 제한했습니다. NBSP/U2003/U3000 quote tail, Unicode pseudoindent/comment, `metadata: {}` 뒤 NBSP는 거부하며 실제 Unicode 문자열 내용은 보존합니다. `name` 뒤 NBSP도 canonical name으로 바꾸지 않고 거부합니다.

`build_package()`의 기존 `collect_files()` 경계를 유지했습니다. 두 원래 반례는 creator 없음/경로 있음 양쪽에서 backend discovery와 invocation 이전에 실패하며 새 output을 만들지 않고 기존 `.skill`, `.zip`과 manifest bytes를 보존합니다. Canonical source 69 files, 정상 metadata map과 scalar가 통과했습니다. 원래 두 반례, Unicode syntax 반례와 정상 metadata/Unicode 문자열은 설치된 Ruby `YAML.safe_load` 판정과 일치했습니다. 기존 package suite에 3개 regression method를 추가했습니다.

새 production dependency를 추가하지 않았습니다. 실제 stdlib archive의 exact source bytes와 extraction round-trip도 검증했습니다. CONTRIBUTING에 subset과 작성 규칙을 명시했습니다.

**Verification limit:** 두 interpreter에 PyYAML이 없어 실제 creator backend 실행은 `NOT_RUN`입니다. 양쪽 creator-path 설정에서 동일 preflight가 먼저 거부함을 source와 invocation 차단 검사로 확인했으며 실제 creator packaging 성공으로 표현하지 않습니다. 전체 YAML 문법을 지원하는 parser가 아닙니다. Actual Codex/Claude malformed-Skill loading과 release는 `NOT_RUN`입니다.

## BROLL-QA-009

**Summary:** Preserve native keyboard activation in review controls
**Priority:** P2 · **Type:** Defect · **Component:** Viewer / compare interaction
**Confidence:** High · **Labels:** `keyboard`, `accessibility`
**Status:** Resolved — locally verified, 2026-10-12

### Current State

**Original observation:** `[Verified]` Document-level Space handler가 focused button에서도 `preventDefault()`와 play click을 수행했습니다. Sound 버튼에 focus한 사용자는 Space로 sound를 켤 수 없고 playback만 바뀌었습니다. Viewer는 INPUT만 제외하며 compare는 control target을 구분하지 않았습니다.

**Evidence:** [viewer template](../skills/broll-me/templates/viewer.html), lines 96–101; [compare template](../skills/broll-me/templates/compare.html), lines 111–124.

### Reproduction and impact

1. 실제 생성된 viewer 또는 compare를 Chromium에서 열고 video를 pause합니다.
2. `Sound on` 버튼에 keyboard focus를 두고 Space를 누릅니다.
3. 두 화면 모두 버튼 text는 `Sound on` 그대로이고 play label만 `Pause`로 바뀝니다.

두 template의 실제 browser 동작으로 재현했습니다. Keyboard-only 사용자는 표시된 button의 native activation을 사용할 수 없습니다.

### Expected State

Interactive control의 native keyboard 동작을 우선하고, background/player shortcut만 해당 범위에서 작동해야 합니다.

**Acceptance Criteria**

1. Focused Sound 버튼에서 Space가 sound를 한 번 toggle하고 playback을 바꾸지 않습니다.
2. Focused Prev, Next, layout 버튼과 checkbox도 native 동작을 유지합니다.
3. Background에서 Space play/pause와 arrow navigation을 유지하고 focus된 seek slider의 동작은 명확하게 구분합니다.

**Original verification limit:** Chromium의 실제 key activation을 확인했습니다. Screen reader 사용과 전체 WCAG 적합성은 `NOT_RUN`이었습니다.

### Resolution — 2026-10-12

두 template의 document shortcut은 native/ARIA controls, editable 영역, modifier 조합, composing 또는 이미 처리한 event에서 반환합니다. Background Space와 arrow 동작은 유지합니다. Compare의 focus된 seek slider는 자체 handler에서 Arrow ±2초를 한 번 처리하며 Space로 재생을 toggle하지 않습니다. Slider의 duration 값과 keyboard focus 표시도 실제 control에 맞췄습니다.

실제 Chromium에서 viewer의 Sound, Prev/Next, clip list button과 Auto checkbox에 Space를 눌러 native 동작을 확인했습니다. Sound는 mute를 한 번 바꾸고 paused 상태를 유지합니다. Compare의 Sound와 Stacked/Wipe button도 해당 control만 동작합니다. Focused slider의 ArrowRight는 1초→3초로 한 번 이동하며 Space는 playback을 바꾸지 않습니다. 두 페이지의 background Space와 arrow navigation도 유지됩니다.

기존 `scripts/check_review_pages.js`에 이 행동 검사를 추가했습니다. 390px/1280px에서 두 페이지 모두 통과했고 실제 media readiness와 seek 완료를 기다려 검사합니다. Generated fixture의 literal metadata와 Korean font loading 검사도 유지합니다.

**Verification limit:** Pinned Chromium의 synthetic local pages와 실제 key activation 근거입니다. Screen reader, 전체 WCAG 적합성, 다른 browser/OS, 실제 host 평가와 사람의 전체 편집 승인은 `NOT_RUN`입니다.

## BROLL-QA-010

**Summary:** Show a recoverable media error instead of a false playback state
**Priority:** P2 · **Type:** Defect · **Component:** Review UI state / observability
**Confidence:** High · **Labels:** `error-state`, `media-delivery`
**Status:** Resolved — follow-up locally verified, 2026-10-12

### Current State

**Reopened observation:** `[Verified]` Missing-media 표시와 Retry는 유지되지만 compare의 waiting 상태에서 재생을 중지할 수 없는 회귀가 있습니다. Loading이 transport를 disable하며 active pair는 계속 재생합니다.

**Original observation:** `[Verified]` Viewer는 `vid.play().catch(()=>{})`로 실패를 숨기고 `Pause`를 즉시 표시했습니다. Media error listener가 없어 파일 누락, unsupported codec 또는 rejected playback 때 빈 화면과 정상 control이 남았습니다. Compare도 play 실패를 무시하며 실제 재생 상태와 무관하게 label을 바꿨습니다.

**Evidence:** [viewer template](../skills/broll-me/templates/viewer.html), lines 90–100; [compare template](../skills/broll-me/templates/compare.html), lines 105–110.

### Reproduction and impact

1. 정상 생성 viewer를 실제 Chromium에서 엽니다.
2. Video source를 같은 scratch directory의 존재하지 않는 `missing.mp4`로 지정합니다.
3. `MediaError.code=4`, `paused=true`, play label `Pause`이며 사용자에게 오류 안내가 없는 것을 확인했습니다.

Missing source는 viewer에서 직접 재현했습니다. Compare의 실패 처리 부재는 source에서 확인했습니다. 결과물을 이동한 뒤 media reference가 끊겨도 사용자에게 파일 문제와 정상 검정 frame의 차이를 알려 주지 않습니다.

### Expected State

Media loading, playing, paused, ended, error 상태를 actual media events와 맞추고 실패한 reference와 복구 행동을 보여 줘야 합니다.

**Acceptance Criteria**

1. Missing/unsupported media에서 읽을 수 있는 error, 실패한 local reference와 retry 또는 다른 clip 선택을 제공합니다.
2. 실패·pause 상태에 `Pause`를 표시하지 않고 불가능한 control을 적절히 disable합니다. 다른 정상 clip으로 이동할 수 있어야 합니다.
3. Viewer와 compare가 같은 상태 계약을 적용하며 정상 playback·seek·sound 동작을 유지합니다.
4. Active pair의 loading/waiting 중에는 함께 pause하거나 실제 재생 중인 pair를 Pause/Space로 멈출 수 있어야 합니다. 검토 시점과 timeline/control 상태를 맞추고 정상 ready 전환도 확인합니다.

**Original verification limit:** Missing-media browser case만 직접 실행했습니다. 실제 codec별 failure와 compare missing-media 재현은 당시 후속 수정 검증 대상이었습니다. [Original screenshot](qa-2026-10-12-assets/viewer-missing.png).

### Resolution — 2026-10-12

두 template은 실제 loading/playing/pause/ended/error events와 playback Promise 결과로 controls를 갱신합니다. Loading/error에서는 `Play`를 표시하며 필요한 transport를 disable합니다. Viewer의 Prev/Next/list와 compare의 layout 선택은 유지합니다. 실패한 reference를 `textContent`로 표시하고 `Retry media`로 같은 source를 다시 load합니다. Compare는 active pair가 준비돼야 재생·seek를 허용하고 Retry 시 검토 시점을 보존하며 수동 Play를 기다립니다.

Viewer는 clip generation으로 이전 Promise 실패가 새 clip을 오염시키지 않게 합니다. Compare는 active pair와 play epoch를 사용하며 RAF마다 실패한 재생을 재시도하지 않습니다. `NotAllowedError`는 수동 Play 안내로 구분하며 `AbortError`는 stale playback 실패로 표시하지 않습니다.

실제 Chromium에서 존재하지 않는 MP4와 unsupported bytes를 두 페이지에 지정했습니다. 읽을 수 있는 오류와 실패 경로가 보이고 Play는 `Pause`로 표시되지 않습니다. Viewer는 정상 clip으로 이동할 수 있으며 오류가 지워집니다. File을 정상 MP4로 복원하고 Retry하면 두 페이지가 정상 상태로 돌아옵니다. Compare Side/Wipe의 실패 상태와 transport/seek 제한도 확인했습니다. Mobile error 상태에 overflow가 없고 status text와 Retry를 시각 확인했습니다. [Viewer](qa-2026-10-12-assets/viewer-media-error.png), [compare](qa-2026-10-12-assets/compare-media-error.png).

별도 Chromium page context의 controlled playback Promise로 compare의 sibling pending+NotAllowed rejection, 약 2초 Retry 보존과 viewer의 Next 이후 stale rejection을 확인했습니다. 실제 browser autoplay 거부나 모든 codec decoder failure와는 구분합니다.

기존 browser checker를 확장했으며 새 framework/dependency는 추가하지 않았습니다. Usage, paired workflow와 troubleshooting에 focus 경계, 실패 reference 복구, Retry와 수동 Play를 명시했습니다.

**Verification limit:** Local missing/unsupported-file failure와 정상 재생·retry는 실제 browser/media 동작입니다. Promise rejection 순서 검사는 controlled fault이며 실제 autoplay policy 거부의 근거가 아닙니다. 전체 codec별 decode failure, screen reader, 다른 browser, 실제 host와 사람의 전체 playback 승인은 `NOT_RUN`입니다.

### Final review — Reopened, 2026-10-12

[compare.html](../skills/broll-me/templates/compare.html), lines 150/153은 loadstart/waiting에서 loading/playing 상태만 갱신합니다. Lines 110–116은 active pair가 unavailable이면 Play와 Sound를 disable하지만 pair를 pause하지 않습니다. 이 waiting 경로는 현재 QA-010 diff에서 도입됐습니다.

실제 로컬 pair를 재생한 뒤 `vA`에 controlled waiting event 하나를 주입했습니다. Master time은 300ms 동안 `0.024826 → 0.327362`초로 증가했고, Space 이후에도 `0.654919`, `paused=false`였습니다. 화면은 disabled Play와 Loading을 표시했으며 slider 값은 `0.0`에서 멈췄습니다. User에게 보이는 stop action과 review time이 실제 영상 상태와 어긋납니다.

**Required correction:** Active pair가 unavailable로 전환될 때 pair의 재생과 stop action을 일관되게 처리합니다. Stale/inactive events가 현재 pair를 바꾸지 않게 하고 waiting → ready 복구에서 timeline과 기존 manual Retry 계약을 유지합니다. 기존 checker의 loading/playing case에 bounded coverage를 보완합니다.

**Verification boundary:** Actual media/browser와 controlled event-handler fault입니다. 실제 network buffering 재현으로 주장하지 않습니다. 앞선 HTTP starvation 시도는 초기 readiness timeout 2회로 결함 판정에 사용하지 않았습니다. 이번 review에서 implementation은 수정하지 않았습니다.

### Follow-up resolution — 2026-10-12

Active waiting/loadstart/emptied는 pending play epoch를 무효화하고 pair를 함께 pause하며 master 검토 시점을 유지합니다. Inactive loading은 현재 pair의 재생·timeline을 바꾸지 않습니다. Ready가 되면 transport를 복구하지만 재생은 수동 Play를 기다립니다. Retry의 저장 시점과 기존 native control/layout 계약은 유지하며 지연된 playing/pause event는 실제 paused 값과 맞지 않으면 상태를 덮어쓰지 않습니다.

고친 원본 browser checker가 390px/1280px 네 화면에서 통과했습니다. Side/Wipe의 active/inactive waiting/loadstart/emptied, 시점 유지, loading 중 Space와 stale playing, readiness 후 manual Play를 확인했습니다. 별도 reviewer probe 두 사례에서 waiting 후 stale NotAllowed rejection, 정상 playback 중 stale pause와 실제 missing-file Retry도 통과했습니다. Retry는 양쪽 영상과 reviewTime 2초를 보존하고 paused 상태로 복구했습니다. Page error는 없습니다.

**Verification limit:** Pinned Chromium, 실제 local media와 controlled events/Promise rejection입니다. 실제 network starvation이나 browser autoplay policy, 모든 runtime/codec, host/editor approval의 근거로 확대하지 않습니다. 이전 readiness timeout 기록은 유지합니다.

## BROLL-QA-011

**Summary:** Honor custom overdamping while preserving fragment inputs
**Priority:** P3 · **Type:** API limitation · **Component:** Motion helper contract
**Confidence:** High · **Status:** Resolved — locally verified, 2026-10-12
**Labels:** `custom-fragment`, `motion-api`

### Current State

**Original observation:** `[Verified]` Scene validation은 모든 finite non-negative damping을 허용했습니다. `M.S()`는 `z >= 1`을 모두 critical damping 식으로 계산해 overdamping 값이 무시됐습니다. `spring:[1,2]`는 허용된 configuration이었습니다.

**Evidence:** [motion.js](../skills/broll-me/engine/motion.js), lines 14–18, 109; [public helper reference](../skills/broll-me/reference/engine-api.md), lines 75–84.

### Reproduction and impact

Exported helper에서 `M.S(1,1,1)`과 `M.S(1,1,2)`를 실행했습니다. 두 값이 모두 `0.26424111765711533`입니다. `z >= 1` 범위에서 damping을 바꿔도 custom animation의 response가 변하지 않습니다. 기본 preset에는 `z > 1`이 없어 기본 template 결함으로 표현하지 않습니다.

### Expected State

사용자 결정에 따라 허용한 finite `z > 1`을 실제 overdamped 계산에 반영합니다. 기존 `[w,z]` 입력, validator 범위, preset과 public API를 유지하며 새 입력 제한이나 migration을 요구하지 않습니다. Custom fragment의 `z > 1` 결과가 이전 critical response와 달라지는 점을 문서에 명시합니다.

**Acceptance Criteria**

1. `z > 1`은 damping 값에 맞는 monotone response를 생성하며 `M.S(1,1,2)`가 약 `0.17773657609819048`로 계산됩니다.
2. 기존 preset, `z < 1`, critical damping과 `Infinity` reset 계약을 유지합니다.
3. 지원 범위와 migration이 두 실행 경로의 문서·validator에 일치합니다.

**Original verification limit:** 실제 helper 수치와 validation을 확인했습니다. `z > 1`을 사용하는 외부 사용자 fragment 수는 `[Unverified]`였습니다.

### Resolution — 2026-10-12

`M.S()`에 finite overdamped 입력을 계산하는 `z > 1` branch를 추가했습니다. Normalized decaying roots, `Math.expm1`과 작은 값의 series로 cancellation 및 중간 overflow를 줄입니다. 기존 `z < 1`, `z === 1`, `tau <= 0`, `Infinity` reset branch와 모든 preset/validator는 변경하지 않았습니다.

원래 반례는 이제 `M.S(1,1,2)=0.1777365760981905`, critical 값은 기존 `0.26424111765711533`입니다. 독립 Decimal 800자리 root-response와 root가 재확인한 14개 입력을 비교했습니다. Near-critical, 작은 시간, 큰 finite damping, `w*tau` overflow와 mixed magnitude에서 finite/bounded 결과를 확인했습니다. Reviewer의 별도 19개 선택 사례에서도 blocker는 없었습니다. 기존 6개 preset과 `z=0`, `.999`, `1`의 총 63개 sample은 이전 source와 `Object.is`로 일치합니다.

기존 Node suite에 4개 regression을 추가했습니다. 독립 기대 수치, monotonicity와 critical limit, 정확한 preset/reset 값, default/per-key `M.track` 및 `M.ctrack`의 damping·seek-order와 authored config 허용을 검사합니다.

기존 fragment 문법으로 `spring:[1,2]`, `camSpring:[1,2]` scene을 build했습니다. Actual Chromium에서 320×180, 1초 scene의 `seek(0)`, `seek(1)`, `seek(.5)`, `seek(1)`을 확인했고 마지막 두 1초 geometry가 동일합니다. 1초 shape width `124.883px`, camera scale `1.08887`은 새 response를 반영합니다. CLI check, 3-frame draft MP4 render·decode가 통과했습니다.

Engine API와 usage에 damping 범위와 호환성, 재검토 안내를 갱신했습니다. Input migration은 필요하지 않지만 기존 `z > 1` fragment의 settling timing은 실제 damping에 맞춰 달라집니다. 원본 fragment를 자동 수정하거나 기존 output을 교체하지 않았습니다.

**Verification limit:** JavaScript Number 계산이며 최저 subnormal에서는 1 ULP 수준의 underflow가 가능합니다. 선택한 입력과 synthetic fragment의 근거이며 모든 finite 입력에 대한 임의 정밀도 보장은 아닙니다. 기존 `period` 알고리즘은 변경하지 않았으며 더 강한 periodicity 계약을 주장하지 않습니다. 실제 host, 외부 custom fragment 전체, human playback·editor approval와 release는 `NOT_RUN`입니다.

## BROLL-QA-012

**Summary:** Wait for the actual media error before asserting its reference
**Priority:** P3 · **Type:** Defect · **Component:** Review-page verification tooling
**Confidence:** High · **Labels:** `test-synchronization`, `error-state`
**Status:** Resolved — follow-up locally verified, 2026-10-12

### Current State

**Original observation:** `[Verified]` [check_review_pages.js](../scripts/check_review_pages.js), lines 80/88/94은 visible media status와 disabled Play만 기다립니다. Loading도 두 조건을 만족하므로 실제 error listener 전에 failed-source를 검사할 수 있습니다. 현재 누적 diff가 추가한 조건입니다.

### Reproduction and impact

현재 template로 생성한 합성 review pages에 unmodified checker를 실행했습니다. Exit 1이며 line 81에서 expected `/unsupported\.mp4/`, actual `''`의 AssertionError가 발생했습니다. 검사 실패 자체를 runtime의 missing-media 표시 누락으로 판단하면 원인과 검증 결과가 왜곡됩니다.

같은 script의 임시 사본에서 세 wait만 visible Retry와 현재 fixture의 failed-source까지 기다리도록 바꿨습니다. 동일 pinned Chromium과 pages의 390px/1280px 네 사례가 통과했습니다. 임시 사본은 저장소에 반영하지 않았으며 원본 명령의 PASS 근거로 사용하지 않습니다.

### Expected State

Missing/unsupported fixture의 actual error transition과 현재 source reference가 확정된 후 assertion을 실행합니다. Loading 상태를 error로 취급하지 않아야 합니다.

**Acceptance Criteria**

1. 각 failed-source assertion 전에 actual error/Retry와 해당 fixture의 reference를 기다립니다. Arbitrary sleep으로 대체하지 않습니다.
2. Loading → error 전환에서도 premature assertion이 발생하지 않고 기존 missing/unsupported/Retry, native keyboard와 responsive 검사를 유지합니다.
3. 고친 원본 checker를 current-template fixture에서 다시 실행해 성공을 확인하며 기존 실패 기록을 보존합니다. 새 dependency나 framework는 추가하지 않습니다.

**Verification limit:** Unmodified command 실패 1회와 scratch-only correction probe 성공을 확인했습니다. 다른 browser/runtime와 모든 event ordering을 검증하지 않았습니다. 해당 final review 당시 production UI 코드와 checker는 수정하지 않았습니다.

### Resolution — 2026-10-12

공유 `mediaError(page, source)` wait가 visible status/disabled Play에 더해 visible Retry와 failed-source 목록의 exact current source를 요구합니다. 최초 오류, viewer에서 재선택한 오류와 compare layout 전환의 세 대기에 같은 조건을 사용하며 arbitrary sleep을 추가하지 않았습니다.

Current template로 생성한 synthetic local pages에 고친 원본 checker를 실행해 viewer/compare 390px/1280px 네 사례가 통과했습니다. Missing/unsupported reference와 파일 복원 후 Retry, native keyboard, metadata/font/layout 검사를 유지하며 compare Loading이 error로 오인되지 않음도 확인했습니다. 이전 원본 command의 실패와 scratch-only probe는 historical record로 보존합니다.

**Verification limit:** Current-source script와 pinned Chromium의 관련 사례입니다. 모든 event ordering 또는 다른 browser/runtime를 보장하지 않습니다. 상세 command/result는 `final_review_corrections`에 기록합니다.

## BROLL-QA-013

**Summary:** Protect media inputs against filesystem-equivalent output paths
**Priority:** P1 · **Type:** Defect · **Component:** Media publication / protected-input identity
**Confidence:** High · **Labels:** `input-preservation`, `filesystem-identity`, `case-alias`, `macos`
**Status:** Resolved — locally verified, 2026-10-12

### Current State

**Original observation, before this fix:** `[Verified]` [media.py](../skills/broll-me/scripts/media.py), 당시 line 194의 input guard와 [preview_bundle.py](../skills/broll-me/scripts/preview_bundle.py), 당시 lines 19/24/65의 protected check는 resolved Path 문자열만 비교했습니다. 대소문자를 구분하지 않는 macOS temp filesystem에서 `SOURCE.mp4`와 `source.mp4`는 같은 entry지만 그 비교는 false였습니다.

Actual `atomic_output()`와 `publish_bundle()`는 alias output을 허용해 protected source bytes를 교체했습니다. 이 string-only check는 baseline에도 있었으며 최신 QA-003의 non-regular/shared-font preflight가 도입한 회귀가 아닙니다. Build의 QA-002 `samefile()` check는 해당 alias를 거부하므로 별도 media 결함으로 분류합니다.

### Reproduction and impact

대소문자를 구분하지 않는 scratch filesystem에서 다음 helper-level 반례를 실행했습니다. `media`는 repository의 `skills/broll-me/scripts`를 import path에 두고 불러옵니다.

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from media import atomic_output

with TemporaryDirectory() as directory:
    source = Path(directory) / "SOURCE.mp4"
    output = Path(directory) / "source.mp4"
    source.write_bytes(b"protected source bytes")
    assert output.exists() and source.samefile(output)
    assert source.resolve() != output.resolve()
    with atomic_output(output, inputs=[source], suffix=".mp4") as staged:
        staged.write_bytes(b"generated preview bytes")
    assert source.read_bytes() == b"generated preview bytes"
```

실제 두 probe는 각각 `samefile=true`, `resolved_path_equal=false`, `error=null`, `source_changed=true`였습니다. Bundle은 stage의 lowercase output을 uppercase protected source와 같은 entry로 publish했습니다. Helper의 `.previous/source.mp4` backup은 관찰됐으며, 정상 `create_bundle()`의 성공 cleanup이 해당 stage를 삭제하는 것은 source trace(lines 87–90)로 확인했습니다. Full CLI encode/cleanup을 이 사례에서 실행한 것은 아닙니다.

Source bytes 교체는 실제 filesystem에서 mock/race/FFmpeg 없이 확인했습니다. Synthetic bytes이며 사용자 media는 변경하지 않았습니다. Distinct hardlink entry의 replace와 달리 source pathname도 새 bytes를 가리키므로 입력 보존 계약을 위반합니다.

### Expected State

Direct media caller/helper와 bundle은 filesystem 기준 같은 protected-input entry로 향하는 output을 첫 mutation 전에 거부하고 inputs와 이전 outputs를 보존해야 합니다. String equality 또는 일괄 casefold를 filesystem identity 검사로 취급하지 않아야 합니다.

**Acceptance Criteria**

1. 위 atomic/bundle alias counterexamples를 거부하고 source·기존 output bytes를 보존합니다. Direct caller preflight에도 같은 정책을 적용해 encoder/staging write 이전에 중단합니다.
2. 실제 filesystem semantics에 맞는 identity check를 사용합니다. Case-sensitive filesystem의 서로 다른 파일을 이름만 비슷하다는 이유로 같은 input으로 취급하지 않습니다.
3. 정상 별도 output, readable input symlink와 macOS temp roots를 유지합니다. Distinct hardlink output 정책은 명시하고 관련 source 보존 사례를 검증합니다.
4. 기존 delivery suite에 조건부 filesystem alias fixture와 정상 비교 사례를 보완합니다. Bundle은 backup 생성 전에 거부하며 release와 외부 파일을 변경하지 않습니다.

**Initial verification limit:** 발견 당시에는 macOS temp filesystem의 helper/publication 두 반례만 실행했습니다. Unicode normalization, case-sensitive filesystem matrix, 실제 full CLI encoding과 release/host/editor acceptance는 당시 `NOT_RUN`입니다. 수정 후 실행 범위는 아래 Resolution에 구분합니다.

**Initial evidence record:** `post_preflight_final_review`의 `case_alias` / `bundle_case_alias`. 발견 당시 review에서는 code/test를 수정하지 않았습니다.

### Resolution — filesystem identity protection, 2026-10-12

`[Verified]` `validate_output_path(..., inputs=...)`가 resolved path와 실제 `samefile()`을 함께 확인합니다. 문자열 casefold를 사용하지 않습니다. `atomic_output()`은 inputs를 tuple로 보존하고 임시 파일 생성 전 및 publication 전에 재검사합니다. `make_pages()`는 plan·source·preview·clips에 대해 고정 page와 panel output 전체를, `inspect_video()`는 source에 대해 contact/report 전체를 첫 encoder/font write 전에 검사합니다.

`create_bundle()`의 요청 MP4는 source·plan·clip identity 충돌을 directory/staging 생성 전에 거부합니다. `publish_bundle()`은 모든 final destination을 첫 backup 전에 검사하고 파일별 publication 직전에도 재검사합니다. Late validation 실패는 `OSError`와 같이 journal rollback을 실행하며 복원 실패 시 기존 recovery 계약을 유지합니다. 파생 파일의 전체 검사는 staging 후 publication 전에 수행합니다.

**Hardlink policy:** Protected input과 inode가 같은 distinct hardlink output도 거부합니다. 기존 build의 보수적 정책과 일치하며 media의 이전 safe hardlink replacement 허용은 유지하지 않습니다. Readable input symlink와 macOS `/tmp`·`/var`의 표준 alias는 유지합니다. Output은 별도 file identity를 사용해야 합니다.

| Verification | Result |
| --- | --- |
| 기존 atomic/bundle 실제 case alias 반례 재실행 | PASS: `samefile=true`, resolved equality false인 상태에서 `MediaError`; source unchanged, renderer 미진입, `.previous` backup 없음 |
| 기존 delivery suite에 추가한 9개 검사 | 8 passed·1 skipped: case alias의 source·plan·clip·preview 보호, zero directory/temp/encoder/font/backup calls, hardlink 거부와 source 보존, atomic late guard, bundle late identity rollback 통과 |
| `make check PYTHON=.runtime/motion/.venv/bin/python` | PASS: package 69 files, Python 109 중 108 passed·1 skipped, Node 25 passed |
| 실제 direct composite / CLI preview alias | PASS: exit 1, protected inputs SHA-256 보존, temporary/staging write 없음 |
| 실제 CLI 정상 preview | PASS: exit 0 / `status:completed`; 6초, 640×360, 30 FPS, viewer/compare/TIMING와 font/notice 5개, source·plan·clips 보존 및 stage cleanup |
| Temporary package | PASS: stdlib-curated 두 archive exact source bytes/extraction; 기존 `dist/` 보존 |

Case-only distinct files의 case-sensitive fixture는 현재 filesystem에서 만들 수 없어 1개 생략했습니다. 이름만 다른 파일을 casefold로 차단하지 않는 것은 source에서 확인했으며 해당 filesystem의 runtime 검증으로 표현하지 않습니다. Unicode normalization alias, hostile interleaving/OS interruption matrix, 새 browser/host/editor acceptance와 release는 `NOT_RUN`입니다. Full CLI **정상 encoding**은 실행했고 full CLI alias **거부**는 encoding 전 중단을 확인했습니다. No new dependency/test framework, commit/push 또는 외부 tracker write입니다.

원래 반례·이전 12건의 결과는 보존합니다. 새 command results, source digest, archive hashes와 초기 파일 보존은 `qa013_identity_follow_up`에 기록합니다.

## BROLL-QA-014

**Summary:** Reject protected HTML input identities before Node contact-sheet publication
**Priority:** P1 · **Type:** Defect · **Component:** Node runtime / beats publication
**Confidence:** High · **Labels:** `input-preservation`, `hardlink`, `filesystem-identity`, `contact-sheet`
**Status:** Resolved — locally verified, 2026-10-12

### Current State

**Original observation, before this fix:** `[Verified]` [runtime.js](../skills/broll-me/engine/runtime.js), 당시 lines 39–44의 `outputFile()`은 realpath 문자열만 비교했습니다. 별도 pathname의 `contact.png`가 HTML source의 hardlink이면 device/inode는 같아도 문자열 비교는 다릅니다. [beats.js](../skills/broll-me/engine/beats.js), 당시 lines 17–30은 이를 허용하고 `copyFileSync(temporary, output)`로 같은 inode를 truncate했습니다.

Actual filesystem과 controlled browser/encoder를 사용한 reviewer probe에서 production `beats()`가 source bytes를 교체했습니다. Root는 별도의 정상 built scene과 hardlink output으로 고정 Chromium·FFmpeg를 실행해 같은 결과를 확인했습니다. Exit 0 / `status:captured`, output은 640×360 PNG였으며 protected HTML pathname도 PNG bytes를 가리켰습니다. Input SHA-256은 `d803afced041c5409772089c3e3e5c32080fb4d242bb3ce9b06affefb9dc2a39`에서 `c0c1f55fab8767556bc33815f822ee1b152e34e11ad31533751f60c295f294a3`로 바뀌었고 source/output은 여전히 같은 inode였습니다.

이 `outputFile()` guard와 `beats.js` publication은 baseline `2ba30a6`에도 있었습니다. QA-013의 Python helper 수정으로 도입된 회귀가 아니며 그 티켓의 source·plan·clip·preview 보호를 재개방하지 않습니다. Repository source와 사용자 media는 건드리지 않은 scratch 재현입니다.

### Reproduction and impact

유효한 built HTML을 별도 scratch directory에 생성한 뒤 `os.link(scene, contact_png)`로 연결합니다. 다음 command가 성공하면서 scene 자체가 PNG로 바뀝니다. `WORK`는 이 synthetic scratch directory이며 사용자 파일에 실행하지 않습니다.

```bash
BROLL_RUNTIME="$PWD/.runtime/motion" node skills/broll-me/engine/beats.js \
  "$WORK/palette-demo.html" "$WORK/contact.png" 0.1
```

Readable HTML source의 내용과 후속 check/render 가능성을 잃습니다. Successful contact-sheet 응답이나 encoder 완료는 입력 보존의 근거가 아닙니다. 첫 real-browser 시도는 sandbox의 Chromium `bootstrap_check_in ... Permission denied (1100)`로 차단됐고 입력은 보존됐습니다. 허용된 동일 runtime 실행에서 손상을 확인했으므로 환경 차단을 제품 성공으로 계산하지 않았습니다.

### Expected State

Node contact-sheet output은 staging·screenshot·encoder 및 output-directory write 전에 protected HTML input의 filesystem identity를 검사하고 충돌을 거부해야 합니다. Publication도 입력과 inode를 공유하는 destination을 truncate하지 않도록 보호해야 합니다.

**Acceptance Criteria**

1. Distinct hardlink PNG output을 거부하고 HTML input, 기존 output bytes와 link identity를 보존합니다. 최초 output/temp write 및 encoder 이전에 중단합니다.
2. Resolved pathname뿐 아니라 실제 filesystem identity를 검사하고 publication 전에 재검사합니다. 입력 inode를 truncate하는 copy 경로에 의존하지 않습니다.
3. 정상 별도 PNG 생성, 기존 contact-sheet dimensions/times, cleanup과 진단을 유지합니다. Input symlink와 hardlink output의 정책을 명시합니다.
4. 기존 Node/runtime test suite의 실제 hardlink fixture와 정상 비교 사례로 검증합니다. 실패 검증이 source 손상이나 불필요한 browser/encoder 실행을 만들지 않아야 합니다.

**Initial verification limit:** 발견 당시 실제 Node/Chromium/FFmpeg helper execution입니다. Common CLI wrapper의 별도 재실행, 모든 output alias 유형과 OS/race matrix는 당시 `NOT_RUN`입니다. Reviewer doubles와 root actual pipeline을 구분합니다.

**Evidence record:** `post_identity_final_review.beats_input_identity`; 관련 source, 최초 browser block 및 actual retry result를 보존합니다.

### Resolution — Node identity guard and safe publication, 2026-10-12

`[Verified]` Pure `validateOutputPath()`는 기존 suffix/path 검사와 bigint `dev`·`ino` identity 비교를 수행하며 directory를 만들지 않습니다. `outputFile()`은 이 guard 통과 후에만 directory를 생성합니다. `beats()`는 browser를 열기 전에 같은 guard로 보호된 HTML input을 거부합니다. Shared output helper의 identity 보호는 render caller에도 적용되며 정상 경로는 기존 계약을 유지합니다.

Stage는 output parent의 `.broll-beats-*`에 생성해 같은 filesystem에서 rename합니다. Capture·encode 실패는 prior output을 보존합니다. Encoder stop과 browser close를 각각 시도하고 둘 다 성공한 뒤 identity를 다시 확인해 PNG directory entry를 교체합니다. Cleanup 실패는 게시를 막으며 staging 제거도 시도합니다. 오류는 sheet의 published/not-published 상태와 inspect할 staging path를 보고합니다.

**Compatibility:** Readable HTML input symlink를 유지하며 protected input과 inode가 같은 output hardlink는 거부합니다. Node의 기존 parent-path 및 관련 없는 output symlink 허용 여부는 유지합니다. Publication은 copy에서 rename으로 바뀌어 관련 없는 symlink target이나 이전 PNG의 observer hardlink inode를 truncate하지 않습니다. Python output symlink 정책을 Node에 새로 확대하지 않았습니다.

| Verification | Result |
| --- | --- |
| Existing runtime suite에 4개 검사 추가 | PASS: hardlink 최초 guard, input symlink·기존 PNG observer 보존, cleanup 후 late alias 거부, capture/encoder/cleanup 실패 보존과 남은 resource cleanup |
| Actual common CLI hardlink counterexample | PASS: exit 1 / `status:error`, source SHA-256·hardlink 보존, browser/encoder 진입 없이 staging 없음 |
| Actual common CLI normal `beats` | PASS: readable input symlink, pinned Chromium·FFmpeg, times 0.1/0.4, 640×360 tile 두 개의 1284×360 PNG, `status:completed`, input/observer hashes 보존 및 staging cleanup |
| Full `make check` | PASS: Python 112 중 110 passed·2 skipped, Node 29 passed, package 69 files |

New browser/version/dependency는 설치하지 않았습니다. Capture·encoder·cleanup 및 late identity 실패 검사는 controlled doubles와 actual filesystem이고 정상 CLI capture는 actual browser/encoder입니다. 모든 output alias·OS/fault/hostile race matrix와 host/editor/release acceptance는 `NOT_RUN`입니다. First check와 rename의 check-to-replace gap을 hostile-process 보장으로 표현하지 않습니다.

**Resolution record:** `qa014_qa015_follow_up`; original damage evidence는 이전 record로 보존합니다.

## BROLL-QA-015

**Summary:** Reject filesystem-equivalent destinations across a build batch
**Priority:** P2 · **Type:** Defect · **Component:** Build CLI / batch destination preflight
**Confidence:** High · **Labels:** `output-collision`, `case-alias`, `batch`, `macos`
**Status:** Resolved — locally verified, 2026-10-12

### Current State

**Original observation, before this fix:** `[Verified]` [build.py](../skills/broll-me/engine/build.py), 당시 lines 159–163의 duplicate stem guard는 Python 문자열의 exact equality만 검사했습니다. 서로 다른 두 directory의 `Intro.html`과 `intro.html` source는 다른 inode이며 이름도 서로 다른 문자열입니다. Case-insensitive filesystem의 단일 outdir에서는 두 `.html` destination이 같은 entry로 향하지만 batch preflight가 통과했습니다.

실제 CLI는 exit 0과 두 `built ...` message를 반환했습니다. Output `.samefile()`은 true, resolved path equality는 false였으며 physical HTML은 1개뿐입니다. 두 output pathname 모두 두 번째 scene을 가리키며 첫 scene은 사라졌습니다. Source hashes는 보존됐고 output palette는 선택한 preset과 일치했습니다. Exact stem guard와 output derivation은 baseline에도 있어 QA-013 회귀가 아닙니다.

### Reproduction and impact

Distinct scratch dirs `batch-input-a/Intro.html`과 `batch-input-b/intro.html`에 서로 다른 title의 정상 fragment를 저장하고, case-insensitive filesystem에서 다음 batch를 실행합니다.

```bash
.runtime/motion/.venv/bin/python skills/broll-me/engine/build.py "$WORK/batch-output" \
  "$WORK/batch-input-a/Intro.html" "$WORK/batch-input-b/intro.html" --font-mode shared
```

각각 FIRST/SECOND scene으로 표시했으며 실제 output에는 SECOND만 남았습니다. Complete-batch duplicate rejection 계약을 위반하고 요청한 첫 산출물을 조용히 잃습니다. Input identity 보호인 QA-002·QA-013과 원인·영향 범위를 분리합니다.

### Expected State

Build CLI는 전체 batch destination의 filesystem-equivalent 이름 충돌을 첫 font/palette/HTML write 전에 거부하고 충돌하는 source와 output을 보고해야 합니다. 해당 filesystem에서 distinct entry인 파일을 이름의 case만으로 차단하지 않아야 합니다.

**Acceptance Criteria**

1. 위 case-equivalent batch를 실패로 처리하고 기존 output·font·palette·source bytes를 보존합니다. 부분 build나 성공 message를 출력하지 않습니다.
2. 아직 존재하지 않는 destination을 포함해 실제 target filesystem의 이름 동등성을 반영합니다. 무조건 casefold를 적용하지 않습니다.
3. 정상 distinct batch와 case-sensitive filesystem의 별도 case-only 이름을 허용합니다. 기존 exact duplicate guard와 shared/embedded font mode를 유지합니다.
4. 기존 palette/build test suite에 조건부 filesystem fixture와 정상 비교 사례를 추가합니다. Multi-file atomic transaction을 새로 요구하지 않습니다.

**Initial verification limit:** 발견 당시 macOS temp filesystem의 실제 Python build CLI입니다. Case-sensitive filesystem, Unicode normalization의 batch collision, common wrapper 재실행과 OS/race matrix는 당시 `NOT_RUN`입니다. Synthetic fragments이며 사용자 파일은 변경하지 않았습니다.

**Evidence record:** `post_identity_final_review.build_output_case_collision`; command/result, source SHA-256과 physical output count를 보존합니다.

### Resolution — target-filesystem batch reservation, 2026-10-12

`[Verified]` `preflight_outputs()`는 모든 destination의 path/input/palette 검사를 마친 뒤 `check_batch_destinations()`를 실행합니다. 각 existing target directory 또는 nearest existing ancestor의 device/inode로 그룹을 만들고, 그 filesystem의 private `.broll-build-preflight-*` 안에 missing relative directories와 **전체 destination 이름**을 exclusive하게 예약합니다. Already-reserved case·normalization alias는 두 source/output을 명시한 오류로 거부합니다. Unconditional casefold를 사용하지 않으며 exact duplicate stem guard도 유지합니다.

**First-write boundary:** 이 검사는 임시 directory와 empty reservation entries를 만들고 정리합니다. 이는 pure read-only check가 아닙니다. Probe가 성공적으로 정리된 뒤에만 최종 font/palette/HTML을 쓰며, 충돌 시 기존 deliverable bytes와 missing final output directory를 보존합니다. Single-output build는 probe를 생략합니다. Cleanup 오류도 실패로 보고하고 final build를 진행하지 않습니다.

| Verification | Result |
| --- | --- |
| Existing palette suite에 3개 검사 추가 | 2 passed·1 skipped: case 및 NFC/NFD collision은 shared/embedded·existing/absent output 모두 exit 2, no built message, prior bytes·input 보존 및 probe cleanup; 정상 distinct batch 두 mode 통과 |
| Actual common CLI original case collision | PASS: exit 2 / `status:error`, final output directory 미생성, 두 source hashes 보존 및 probe 없음 |
| Actual common CLI normal batch | PASS: shared/embedded 모두 exit 0 / `status:completed`, 서로 다른 두 HTML과 각 font-mode 계약 유지 |
| Repository를 수정하지 않은 reviewer의 scratch helper probes | PASS: distinct existing output hardlinks 보존, 255-byte name 허용, absent parent-directory case alias 거부와 probe cleanup |
| Full `make check` / latest palette check | PASS: Python 112 중 110 passed·2 skipped, Node 29 passed; focused palette 22 중 21 passed·1 skipped |

두 생략 test는 QA-013과 QA-015의 case-sensitive case-only distinct-file fixture이며 현재 filesystem에서는 만들 수 없습니다. 실제 case-sensitive volume, 다른 filesystem의 per-directory naming 정책과 OS/race matrix는 `NOT_RUN`입니다. 이번 macOS filesystem의 실제 collation을 확인한 결과를 모든 플랫폼의 보장으로 확대하지 않습니다. 이름 예약에 prefix를 붙이지 않아 기존 최대 filename 길이를 유지하고 distinct hardlink output entry는 충돌로 취급하지 않습니다.

**Resolution record:** `qa014_qa015_follow_up`; prior false-success evidence와 당시 `NOT_RUN`을 보존합니다.

## Closure rules

1. 해당 counterexample과 정상 대표 입력만 최소 재검증합니다. 기존 test suite를 우선하며 별도 framework를 만들지 않습니다.
2. 수정한 ticket의 Current State는 historical observation으로 유지하고 resolution revision과 실제 command result를 추가합니다.
3. `PASS`, `BLOCKED`, `NOT_RUN`을 구분합니다. Ticket close가 human approval, release 또는 실제 host 성공을 자동 의미하지 않습니다.

## Final cumulative review confirmation before QA-013 fix — 2026-10-12

QA-001부터 QA-012는 original acceptance 범위에서 Resolved를 유지합니다. Latest non-regular/shared-font preflight, native controls와 loading/error/Retry 검사는 통과했으며 implementation은 이번에 변경하지 않았습니다. 신규 QA-013은 기존 media identity 누락으로 독립 등록했고 미해결 1건입니다. Source hashes, 실제 command result와 검증 한계는 `post_preflight_final_review`에 기록합니다. 티켓 해결 상태를 전체 입력 alias·release·human approval의 보장으로 확대하지 않습니다.

## Closure confirmation after QA-013 fix, before final cumulative review — 2026-10-12

QA-001부터 QA-013까지 13건 모두 original acceptance 및 해당 Resolution 범위에서 Resolved입니다. QA-013의 identity 거부, first-write 경계, rollback과 정상 CLI bundle을 검증했습니다. Case-sensitive case-only runtime fixture 1개는 환경 제약으로 생략했고 release·host·human approval는 별도입니다. 이번 작업의 변경 및 검증 record는 `qa013_identity_follow_up`입니다.

## Cumulative review confirmation before QA-014/015 fix — 2026-10-12

QA-001부터 QA-013은 해당 acceptance·Resolution 범위에서 Resolved를 유지합니다. 이번 전체 diff review는 구현과 tests를 변경하지 않았으며 별도 baseline 누락 QA-014(P1)·QA-015(P2)를 Open으로 추가했습니다. 현재 15건 중 13 Resolved·2 Open입니다. Existing suite·현재 template browser·임시 archive 검사는 통과했으나 새 두 counterexample은 아직 미해결입니다. 실제 결과와 최초 browser block, verification limits 및 파일 보존은 `post_identity_final_review`에 기록합니다.

## Resolution confirmation after QA-014/015 fix, before final review — 2026-10-12

QA-001부터 QA-015까지 15건 모두 해당 acceptance·Resolution 범위에서 Resolved입니다. 두 반례의 actual common CLI 거부와 정상 contact-sheet/batch, 기존 suite 및 임시 archive를 검증했습니다. Case-sensitive fixture 2개와 다른 filesystem/hostile race·host/editor/release acceptance는 별도로 남깁니다. Source·기존 변경·media·LICENSE·evidence images·discovery symlinks·`dist/`를 보존했고 최신 record는 `qa014_qa015_follow_up`입니다.

## Final cumulative review confirmation including QA-014/015 — 2026-10-12

전체 diff와 관련 caller를 대조해 QA-001부터 QA-015까지 해당 acceptance·Resolution 범위의 Resolved 상태를 유지합니다. 추가 supported defect·회귀 및 새 티켓은 없습니다. Actual common CLI의 hardlink/case collision 거부·정상 shared batch, 기존 suite, 현재 template browser 네 화면과 최종 archive exact bytes를 재검증했습니다. Case-sensitive fixture 2개는 생략했으며 다른 filesystem/race/host/editor/release는 별도입니다.

이번 review는 구현과 tests를 변경하지 않았고 QA 기록·CONTRIBUTING만 갱신합니다. 직전 actual normal beats·양 font-mode 결과는 당시 근거로 유지하며 새 actual capture로 표현하지 않습니다. 모든 이전 failure/closure와 현재 source·기존 변경·assets·links·`dist/`를 보존했고 최신 검증 record는 `post_firstwrite_final_review`입니다.
