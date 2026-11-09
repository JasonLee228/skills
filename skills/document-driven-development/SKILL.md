---
name: document-driven-development
description: Use when non-trivial feature work, bug fixes, refactoring, or API/DB changes need documented scope, design decisions, and verification evidence, or when the user explicitly requests document-driven development. Skip trivial edits unless requested.
---

# Document Driven Development

설계 문서는 승인된 계약과 이유를, 구현 기록은 현재 상태와 실제 증거를 보존한다. 문서량과 실행 방식은 작업에 맞추되 구현 승인, 검증, 리뷰, 기존 변경 보호는 유지한다.

## 적용 범위와 권한

- 설계 판단, 여러 계층 변경, API/DB/권한/외부 연동 영향이 있는 개발에 적용한다. 오탈자·포맷팅·영향이 명확한 한 줄 변경에는 자동 적용하지 않는다.
- 분석·리뷰만 요청받았다면 읽고 보고한다. 스킬을 언급했다는 이유로 문서 생성, stage, 구현 또는 외부 쓰기를 시작하지 않는다.
- 사용자 지시와 프로젝트 규칙을 우선한다. 이미 승인된 범위는 승인 근거를 기록하고 계속하며, 같은 승인을 다시 받지 않는다.
- 코드 구현은 설계·TODO·검증 범위에 대한 구현 승인 후 진행한다. 개발 승인은 commit/push나 승인되지 않은 외부 변경을 포함하지 않는다.

## 시작과 실행

1. 현재 작업 경로·기존 변경·관련 계약을 확인하고 [workflow-guide.md](references/workflow-guide.md)를 따른다.
2. 설계와 구현 기록을 함께 준비해 승인된 범위를 확정한다. 이미 승인된 작업은 필요한 기록을 보완한다. 로드맵에 이 작업의 행을 추가하거나 상태를 갱신한다.
3. 직접 수행 또는 순차·병렬 위임으로 구현하고, 수용한 결과와 검증 근거를 기록한다.
4. 실제 변경을 검증·리뷰하고 로드맵 상태를 갱신한다. 작업 단위 보고 전 stage하고, 완료 범위와 남은 일을 구분해 보고한다.

설계 선택이 먼저 필요한 작업은 설계 승인과 구현 승인을 나눈다. 일반 작업은 설계·TODO·검증안을 묶어 한 번 승인받는다. 중단·재승인과 stage의 세부 기준은 workflow에만 정의한다.

## 필요한 자료만 읽기

| 상황 | 참조 |
|---|---|
| 문서 위치나 템플릿이 아직 정해지지 않음 | [setup-guide.md](references/setup-guide.md) |
| 파일명·기록 시각·보고 형식 확인 | [naming-and-reporting-guide.md](references/naming-and-reporting-guide.md) |
| 위험도·단계 분할 판단이 필요 | [risk-guide.md](references/risk-guide.md) |
| 구현·조사·검증·리뷰를 SubAgent에게 위임 | [subagent-delegation-guide.md](references/subagent-delegation-guide.md) |
| 검증과 코드 리뷰 수행 | [verification-guide.md](references/verification-guide.md) |
| 신규/수정 API의 명세 반영 | [api-documentation-guide.md](references/api-documentation-guide.md) |
| 현재 상태·이력·별도 리뷰·기술 노트의 기록 위치 결정 | [record-routing-guide.md](references/record-routing-guide.md) |

## 기본 산출물

진행 문서는 `docs/dev_workflow/plans/active/`와 `implementations/active/`에 두고, Task 목록은 `docs/dev_workflow/roadmap.md`에 둔다. 프로젝트에 다른 합의가 있으면 그 위치를 사용한다.

- [설계 템플릿](templates/plan.md): 요구사항·제외 범위, 현재 흐름, 채택 계약과 이유, 위험·검증 전략.
- [구현 기록 템플릿](templates/implementation.md): 현재 상태, TODO, 실제 변경·결정·검증·리뷰·후속 결과.
- [로드맵 템플릿](templates/roadmap.md): `docs/dev_workflow/roadmap.md`에 Task 한 줄(번호·상태·문서 링크·commit)을 둔다. Task 번호는 로드맵이 발급한다. 상세 내용은 plan·impl에만 둔다.
- [리뷰 기록](templates/review-record.md)과 [최종 보고](templates/final-report.md)는 독립 보존이 필요할 때만 분리한다.
- 템플릿은 필요한 항목만 남긴다. 현재 상태와 상세 증거를 여러 표에 복제하지 않는다.

부모 Agent는 승인 범위, DDD 문서, 결과 수용, 통합 검증의 신뢰성, stage와 외부 업데이트를 책임진다. 직접 구현할 필요는 없으며, 하위 Agent의 완료 보고만으로 작업을 완료 처리하지 않는다.

## 다른 실행 스킬과 함께 사용할 때

DDD는 승인·계약·기록·완료 판단을 맡고 실행 스킬은 작업 수행 방법을 맡는다. 기존 plan/impl을 기준으로 필요한 작업 brief만 전달한다. 같은 목적의 계획·진행 문서를 추가하거나 공통 절차·전체 구현 코드를 작업 문서에 복제하지 않는다.

별도 실행 스킬을 사용할 때 해당 작업의 승인 범위, 역할, 리뷰 기준, commit/push 금지 등 프로젝트 제약을 brief에 반영한다. 실행 스킬이 제안하는 자동 commit, 추가 승인, 별도 장부로 기존 권한과 기록 기준을 바꾸지 않는다.
