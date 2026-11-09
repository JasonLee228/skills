# 파일명·시각·보고

## 위치와 파일명

프로젝트의 기존 관례를 우선하며 기본 경로는 다음과 같다.

```text
docs/dev_workflow/roadmap.md
docs/dev_workflow/plans/active/{TaskNum}_{summary}_plan.md
docs/dev_workflow/implementations/active/{TaskNum}_{summary}_impl.md
```

- `TaskNum`: [로드맵](../templates/roadmap.md)이 발급한 정수 번호. 로드맵에서는 `#12`, 파일명에서는 `12`로 쓴다. 번호는 재사용하지 않는다.
- `summary`: 짧은 영문 snake_case.
- 선택 문서는 `reviews/active/..._review.md`, `reports/active/..._final_report.md`.
- 완료 보관은 [workflow](workflow-guide.md#7-완료와-보관)의 승인 기준에 따라 같은 파일명으로 `completed/`로 이동한다.

## 기록 시각

승인·결정·수용·검증·외부 반영 같은 실제 사건은 `yyyy-MM-dd HH:mm`으로 기록한다. 여러 시간대를 쓰면 기준 시간대도 명시한다. 계획된 검사에 가짜 실행 시각을 넣지 않는다.

## 사용자 보고

보고는 판단에 필요한 결과와 다음 행동을 우선한다. 단계별 동일한 장문 서식을 반복하지 않는다.

| 시점 | 필요한 내용 |
|---|---|
| 승인 요청 | plan/impl 링크, 제안 계약·범위·검증, 실제 결정할 항목, stage 상태 |
| 진행 중 | 확인한 사실, 남은 문제, 다음 검증/행동 |
| 단계·개발 완료 | 완료 범위, 주요 검증·리뷰와 한계, stage 상태, 외부 반영/후속 중 중요한 항목 |

이미 받은 승인은 재요청하지 않는다. 보고 전 stage의 적용 시점과 방법은 [workflow](workflow-guide.md#5-보고-전-stage)에 따른다. 짧은 작업은 결과·근거·남은 일을 몇 줄로 보고하면 충분하다.
