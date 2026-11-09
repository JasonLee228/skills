---
name: java-comment-reviewer
description: Java 변경사항의 Javadoc, inline comment, 논리적 빈 줄을 검토한다. Use when reviewing Java comments, Javadoc, code-line spacing, DDD implementation review, or when the user asks for 주석 검증, 코드라인 검증, Javadoc 검토.
version: 1.0.0
---

# Java Comment Reviewer

Java 변경사항을 readonly로 검토한다. 파일 수정, 포맷팅, 리팩터링, 커밋은 하지 않는다.

## 검토 범위

1. 기본 범위는 `git diff` 기준 변경 Java 파일이다.
2. 사용자가 `/document-driven-development`, `/ddd`, 구현 문서, 계획 문서, 특정 파일/폴더를 제공하면 해당 범위의 Java 파일도 포함한다.
3. 구현 문서가 있으면 `docs/dev_workflow/plans/**`, `docs/dev_workflow/implementations/**`에 기록된 변경 파일과 TODO를 우선 확인한다.
4. 생성 파일은 전체 파일을 검토하고, 수정 파일은 변경 hunk와 관련 public/protected surface를 함께 검토한다.

## 기준 규칙

다음 기준 규칙을 적용한다. 프로젝트에 자체 주석·빈 줄 규칙이 있으면 그 규칙을 우선한다.

- [java-documentation-comments.md](references/java-documentation-comments.md)
- [java-logical-vertical-spacing.md](references/java-logical-vertical-spacing.md)

규칙 파일을 읽을 수 없으면 검토를 중단하지 말고, 아래 체크리스트를 기준으로 검토한 뒤 규칙 파일 미확인 사실을 보고한다.

## Javadoc 검토

다음을 결함으로 보고한다.

- 새 public class, interface, enum에 역할과 책임을 설명하는 Javadoc이 없다.
- 새 public/protected method에 목적, 핵심 파라미터, 반환값, 예외 조건 설명이 없다.
- `@param` 이름이 실제 메서드 파라미터와 다르거나, 삭제된 파라미터를 계속 설명한다.
- 실제 파라미터가 있는데 `@param`이 누락되어 계약 이해가 어렵다.
- non-void 반환인데 반환 의미가 불명확하고 `@return` 설명이 없다.
- 명시적으로 던지거나 도메인상 중요한 예외 조건이 있는데 설명이 없다.
- Javadoc 내용이 구현과 맞지 않거나 이전 동작을 설명한다.
- 같은 의미의 문장이 중복되어 Javadoc이 장황하거나 서로 충돌한다.
- DTO, config, external API integration, event, scheduler 등 계약 성격 타입에서 필드 의미 설명이 부족하다.

단순 getter/setter, Lombok 기반 단순 DTO의 자명한 필드는 프로젝트 관례와 변경 위험을 보고 판단한다. 확신이 낮으면 결함이 아니라 `확인 필요`로 분리한다.

## Inline Comment 검토

다음을 결함으로 보고한다.

- Javadoc 또는 inline comment가 프로젝트가 정한 주석 언어(기준 규칙의 기본값은 한국어)가 아니다.
- 고정 외부 식별자, protocol term, API field name, quoted specification text가 아닌 다른 언어 문장이 주석에 남아 있다.
- API key, token, personal data, file Data URL, trace/session data 등 민감 데이터 처리 의도가 코드만으로 드러나지 않는데 주석이 없다.
- fallback, transformation, security reasoning, external contract compliance가 코드만으로 불명확한데 주석이 없다.
- 단순 대입, getter 호출, builder field 나열처럼 자명한 코드에 설명 주석이 붙어 소음이 된다.
- 주석이 실제 코드와 맞지 않거나 삭제된 정책/분기를 설명한다.

## 논리적 빈 줄 검토

다음을 결함으로 보고한다.

- 메서드 안에서 준비, 검증, 직렬화, 요청 구성, 외부 호출, 반환, 예외 처리 단계가 붙어 있어 흐름이 읽기 어렵다.
- `try`, `catch`, `if`, `for` 내부에서 논리 단계가 바뀌는데 빈 줄이 없다.
- 예외 처리와 반환이 앞 단계와 붙어 있어 의미 전환이 흐릿하다.
- 서로 다른 책임의 지역 변수 선언, 도메인 계산, 외부 호출이 한 덩어리로 붙어 있다.

다음은 결함으로 보고하지 않는다.

- fluent chain 또는 builder chain 내부의 줄 간격.
- 한 표현식처럼 읽혀야 하는 밀접한 선언 묶음.
- 기존 파일 스타일과 일관된 아주 작은 메서드에서 빈 줄 추가가 오히려 소음을 만드는 경우.

## SubAgent 실행 지침

이 Skill을 사용하는 상위 Agent는 가능하면 readonly subAgent를 별도로 실행한다.

권장 subAgent 설정:

- 범용(general-purpose) readonly subAgent
- 백그라운드 실행은 사용자가 병렬 검토를 원할 때만

권장 프롬프트:

```text
Java 주석/코드라인 검증 전용 reviewer로 동작하라.

범위:
- git diff 기준 변경 Java 파일
- 사용자가 제공한 DDD 계획/구현 문서에 언급된 Java 파일

기준:
- <skill-dir>/references/java-documentation-comments.md
- <skill-dir>/references/java-logical-vertical-spacing.md
- <skill-dir>/SKILL.md
- 프로젝트 자체 주석 규칙이 있으면 우선 적용

제약:
- readonly 검토만 수행한다.
- 파일 수정, 포맷팅, 리팩터링, 커밋을 하지 않는다.
- 확실한 결함만 findings로 보고한다.
- 애매한 항목은 확인 필요로 분리한다.

검토 항목:
- Javadoc 중복, 누락, stale 내용, 잘못된 @param/@return/@throws
- 주석 언어 기준 위반
- 민감정보/보안/fallback/외부 계약 처리 의도 주석 누락
- 논리 단계 사이 빈 줄 누락 또는 과도한 빈 줄

출력:
- Findings first
- Critical, Major, Minor 순서
- 파일 경로, 심볼 또는 라인 근처 설명, 위반 규칙, 근거, 권장 수정 방향 포함
- 발견 이슈가 없으면 "발견된 주석/코드라인 검증 이슈 없음"이라고 명확히 보고
```

## 출력 형식

검토 결과는 코드 리뷰 형식으로 쓴다.

```markdown
## Findings

- [Major] `path/to/File.java` `methodName(...)`
  - 문제: 실제 파라미터는 `policyId`인데 Javadoc은 삭제된 `ruleId`를 설명합니다.
  - 기준: `java-documentation-comments.md`
  - 권장: `@param` 이름과 설명을 현재 시그니처 기준으로 수정하세요.

## 확인 필요

- `path/to/File.java`: DTO 필드 Javadoc 필요 여부는 팀의 해당 DTO 문서화 수준 확인이 필요합니다.

## 검증 범위

- 변경 Java 파일: N개
- DDD 문서 참조 파일: N개
- 제외: 테스트/생성 코드 등 제외 사유
```

Findings가 없으면 긴 요약을 쓰지 않는다. 검증 범위와 잔여 리스크만 짧게 남긴다.
