# Task #12 - 주문 목록 상태 필터 설계

> 가상 작성 예시. 실제 프로젝트의 현재 계약이나 승인 근거가 아니다.
> 작성시각: 2026-06-08 09:00 · 작성자: DDD Example
> 구현 기록: [예시 impl](12_order_list_status_filter_impl.md)

## 요구사항과 범위

주문 목록 조회 `GET /api/orders`에 `status` 필터를 추가한다. 여러 상태를 콤마로 받아 OR 조건으로 조회한다. 정렬·pagination 계약, 주문 상세 API, 상태 변경 API는 변경하지 않는다.

완료 조건은 필터 계약 구현, 기존 목록 조회 회귀 테스트 통과, 코드 리뷰 finding 해결이다. API 명세 반영은 승인 상태를 별도로 기록한다.

## 현재 흐름과 설계 결정

기존 목록 조회는 controller → `OrderQueryService.list(pageable)` → repository 단일 조회 흐름이다. 상태 enum `OrderStatus`는 5개 값이며 DB 컬럼은 문자열로 저장된다.

`status`는 선택 query parameter로 받고 `OrderListFilter` record로 service에 전달한다. 알 수 없는 상태 값은 400을 반환하고, 빈 값은 필터 없음으로 처리한다. repository는 `findAllByStatusIn`을 추가하고 기존 `findAll` 경로는 유지한다.

기존 `list(pageable)`에 nullable 인자를 덧붙이는 안은 호출부가 늘어날수록 인자 조합이 불명확해져 채택하지 않는다. 필터를 전용 검색 endpoint로 분리하는 안은 소비자가 두 endpoint를 구분해야 해 채택하지 않는다.

```text
GET /api/orders?status=PAID,SHIPPED&page=0&size=20
→ status 파싱·검증 (알 수 없는 값: 400 INVALID_ORDER_STATUS)
→ 필터 없음: 기존 findAll / 필터 있음: findAllByStatusIn
→ 기존 응답 DTO·pagination 그대로 반환
```

## 영향과 검증 전략

| 영향 | 변경 방향 | 검증 |
|---|---|---|
| controller·request 파싱 | `status` 선택 파라미터, 400 계약 | 단일·다중·빈 값·잘못된 값 |
| `OrderQueryService`·repository | 필터 record와 `findAllByStatusIn` | 필터 결과 집합, 필터 없음 회귀 |
| 응답·pagination | 변경 없음 | 기존 목록 테스트 회귀 |

구체적 파일별 작업과 명령은 impl에 둔다.

## API 명세 계획

`GET /api/orders`의 `status` 파라미터와 400 응답을 주문 API 명세에 추가한다. 실제 문서 위치와 외부 쓰기 승인 상태는 실행 시 확인한다.

## 승인

이 가상 시나리오에서는 설계·TODO·검증안을 함께 승인받았다. 시각과 범위는 impl 현재 상태를 참조한다.
