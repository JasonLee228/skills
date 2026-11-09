---
name: api-documentation-manager
description: >
  백엔드 프로젝트(Spring 등)의 API 소스코드를 분석해 Docusaurus 기반 API 명세 문서를 작성하거나, 기존 문서를 업데이트/리팩토링한다.
  사용 시점: "API 명세서 작성해줘", "API 문서 만들어줘", "이 컨트롤러 문서화해줘", "API 스펙 문서 생성해줘", "API 문서 업데이트해줘", "API 문서 리팩토링해줘" 등 API 문서 작성/수정 요청 시.
version: 1.0.0
---

# API Documentation Manager

백엔드 API 소스코드를 분석하여 Docusaurus 기반의 API 명세 문서를 **신규 작성**하거나, **기존 문서를 업데이트/리팩토링**한다.

## 워크플로우

### 1. 기본 정보 수집

#### 1-0. 작업 유형 확인

가장 먼저 작업 유형을 파악한다. 사용자가 명시하지 않은 경우 다음과 같이 질문한다:

> "이번 작업은 어떤 유형인가요?
>
> 1. **신규 작성** — 아직 문서가 없는 API를 새로 문서화
> 2. **업데이트** — API 소스코드가 변경되어 기존 문서를 최신 상태로 갱신
> 3. **리팩토링** — 소스코드 변경 없이 기존 문서의 구조·내용·중복을 개선"

- **신규 작성**: 아래 1-1 → 1-2 순서대로 진행한다.
- **업데이트 / 리팩토링**: [업데이트/리팩토링 워크플로우](#업데이트리팩토링-워크플로우)로 이동한다.

---

#### 1-1. 대상 API 위치 확인

사용자가 대상 API 위치를 명시하지 않은 경우, 다음과 같이 질문한다:

> "문서화할 **대상 API의 위치**를 알려주세요.  
> (예: 특정 폴더, 파일, 또는 특정 엔드포인트 단건 등)  
>
> 예시:
> - 폴더: `src/main/java/com/example/controller/`
> - 파일: `src/main/java/com/example/controller/UserController.java`
> - 특정 API: `UserController.java의 POST /users 엔드포인트`"

#### 1-2. 문서 작성 위치 확인

명세 문서를 저장할 부모 디렉토리를 입력받는다:

> "API 명세 문서를 저장할 **부모 폴더 경로**를 알려주세요.  
> (예: `docs/api`, `documentation/api-specs`, `website/docs/api`)"

---

### 2. 소스코드 전체 분석

입력받은 대상 API 위치를 기반으로 소스코드를 분석한다. **로직 전체**를 추적하여 나타날 수 있는 모든 케이스를 파악하는 것을 원칙으로 한다.

#### 2-1. 엔드포인트 파악

프로젝트 종류에 따라 엔드포인트 정의 방식을 파악한다.

- **Spring 프로젝트**: `@RestController`, `@Controller`, `@RequestMapping`, `@GetMapping`, `@PostMapping`, `@PutMapping`, `@PatchMapping`, `@DeleteMapping` 어노테이션 기반으로 HTTP 메서드 및 URL 경로 확인
- **기타 백엔드 프레임워크**: 라우팅 정의 방식에 맞게 엔드포인트 파악

각 엔드포인트에서 다음을 확인한다:
- HTTP 메서드 및 URL 경로
- Path Variables, Query Parameters, Request Body
- Request Headers (`Authorization`, `Content-Type` 등)
- 권한(Authority) 정보 (Spring Security의 `@PreAuthorize`, `hasRole`, `hasAuthority`, 커스텀 인터셉터 등)

#### 2-2. 요청/응답 객체 분석

**Request 분석**:
- Request DTO / Body 클래스를 찾아 필드명, 타입, 필수 여부, 설명을 파악한다.
  - Spring: `@NotNull`, `@NotBlank`, `@NotEmpty`, `@Valid`, `@RequestBody`, `@RequestParam`, `@PathVariable` 등으로 필수 여부 판단
  - 기본값이 있는 필드는 기본값도 파악한다.

**Response 분석**:
- Response DTO / 반환 객체를 찾아 필드명, 타입, 설명을 파악한다.
- 공통 응답 래퍼(Wrapper) 클래스가 있다면 구조를 함께 파악한다.

#### 2-3. 비즈니스 로직 및 예외 처리 전체 분석

해당 API의 **Service 레이어 → Repository 레이어**까지 전체 로직을 추적한다.

발생 가능한 **모든 예외 케이스**를 파악한다:
- `throw new CustomException(...)`, `@ExceptionHandler`, `GlobalExceptionHandler` 등 예외 처리 클래스 확인
- 각 예외에 대응하는 HTTP Status Code, Error Code, Error Message를 확인한다.
- 권한 검증, 비즈니스 유효성 검증, 데이터 무결성 검증 등 모든 검증 로직에서 발생하는 오류 케이스를 포함한다.

#### 2-4. 불명확한 사항 사용자 확인

분석 중 다음과 같이 불명확한 사항이 있다면, 문서 작성 전에 사용자에게 확인하고 진행한다:
- 오류 코드의 정확한 의미 또는 설명
- 특정 필드의 비즈니스 규칙 및 검증 조건
- 권한(Authority) 체계
- Response Body의 특정 필드 용도

> "다음 사항을 확인해 주세요:  
> 1. `C4001` 오류 코드의 정확한 설명이 무엇인가요?  
> 2. `companyId` 필드는 토큰의 회사 ID와 항상 일치해야 하나요?"

---

### 3. 문서 저장 위치 및 구조 결정

#### 3-1. 기존 도메인 폴더 확인

1-2에서 입력받은 부모 폴더 경로 하위에 있는 기존 폴더 목록과 번호를 확인한다.

- 폴더 명명 규칙: `{숫자}. {PascalCase}` — 번호 뒤에 점(`.`)과 공백(` `)을 붙이고, 도메인 이름은 PascalCase로 작성한다.
  - 예: `1. Certification`, `2. Company`, `29. ScreenMark`, `30. LlmLog`
  - 한 자리 숫자는 제로패딩 없이 그대로 사용한다.
- 기존 도메인의 API를 추가하는 경우: 해당 도메인 폴더에 문서를 추가한다.
- 신규 도메인인 경우: **기존 폴더 최대 번호 + 1**로 새 폴더를 생성한다.

#### 3-2. 신규 도메인 폴더 생성

신규 도메인인 경우, 반드시 신규 폴더를 생성하고 `_category_.json`을 함께 작성한다:

```json
{
    "label": "📁 도메인 한글명",
    "position": 30,
    "link": {
      "type": "generated-index",
      "description": "도메인에 대한 설명"
    }
}
```

- `label`: 이모지 `📁`를 앞에 붙이고 도메인의 **한글 명칭**을 작성한다.
- `position`: 폴더 번호와 동일한 정수값 (기존 폴더 최대 번호 + 1)
- `description`: 해당 도메인의 기능을 간략하게 설명한다.

#### 3-3. 참조 문서(Reference Document) 생성

신규 도메인 문서 작성 또는 기존 도메인 리팩토링 시, 여러 API에서 중복으로 사용되는 항목이 있는 경우 참조 문서를 생성하여 중복을 방지한다.

참조 문서는 내용에 따라 **반드시 두 종류로 분리**하여 작성한다:

| 종류 | 파일명 규칙 | 포함 내용 |
|---|---|---|
| **공통 응답 객체** | `00. {DomainName}.md` | 공통 Response Body 객체, 공유되는 DTO/Enum 등 |
| **공통 에러 코드** | `00. ErrorCodes.md` | 공통 HTTP Status, Error Code, Error Message 목록 |

- **파일명 규칙**: 항상 `00.`으로 시작하여 폴더 최상단에 위치하도록 한다.
- `sidebar_position: 0`으로 설정하여 사이드바 최상단에 표시한다.
- 해당 종류의 중복 항목이 없다면 해당 파일은 생성하지 않는다.

**공통 응답 객체 문서** (`00. {DomainName}.md`) 작성 기준:
- 도메인 내 2개 이상의 API Response Body에서 동일한 객체(DTO)가 반복 사용되는 경우
- 공유되는 Enum 타입 또는 중첩 객체가 있는 경우

**공통 에러 코드 문서** (`00. ErrorCodes.md`) 작성 기준:
- 도메인 내 2개 이상의 API에서 동일한 HTTP Status + Error Code + Message 조합이 반복되는 경우
- 예: 권한 없음(`403 C4005`), 리소스 없음(`404 C4004`) 등 공통 오류

다른 문서에서는 각 참조 문서를 **상대 경로**로 링크한다:

```markdown
공통 응답 스키마: [ResScreenMark](./00.%20ScreenMark.md#res-screenmark)
공통 에러 코드: [에러 코드 참조](./00.%20ErrorCodes.md)
```

---

### 4. 문서 작성

[api-docs-format.md](./api-docs-format.md) 형식을 따른다. 형식이 불명확할 때 [api-docs-example.md](./api-docs-example.md)를 참고한다.

#### 4-1. 파일명 결정

파일명 규칙: `{두 자리 제로패딩 번호}. {PascalCase}.md`

- 번호는 **두 자리 제로패딩**을 사용한다: `01`, `02`, `03`, ... `10`, `11`
- 번호 뒤에 점(`.`)과 공백(` `)을 붙이고, 이름은 **PascalCase**로 작성한다.
- 예: `01. CreateSslCertificate.md`, `02. UpdatePolicy.md`, `03. ListUsers.md`
- 참조 문서(공통 객체·오류 코드 등)는 항상 `00.`으로 시작한다.
  - 예: `00. ScreenMark.md`, `00. ErrorCodes.md`
- 하나의 파일에 하나의 API를 문서화하는 것을 원칙으로 한다.
  - 단, 연관성이 높고 내용이 단순한 API(예: 단순 목록 조회 + 단건 조회)는 하나의 파일에 작성 가능하다.
- 도메인 폴더 내 기존 파일의 최대 번호를 확인하고, 다음 번호를 사용한다.

#### 4-2. Docusaurus Front Matter 작성

각 문서 최상단에 다음과 같이 작성한다:

```markdown
---
sidebar_position: 1
title: API 제목
tags:
  - 도메인태그
  - 추가태그
---
```

- `sidebar_position`: 도메인 폴더 내 문서 순서 (기존 문서 확인 후 다음 번호 사용)
- `tags`: 도메인명, 기능 관련 키워드

#### 4-3. 각 섹션 작성

분석한 소스코드 정보를 바탕으로 다음 섹션을 작성한다:

- **제목 및 요약**: API의 핵심 동작을 한 줄로 요약하고, 주요 동작을 bullet로 나열한다.
- **Request**:
  - URL (HTTP Method + Path)
  - Headers (필요한 것만 — Authorization, Content-Type 등)
  - Authority (권한이 있는 경우)
  - Path Variables (있는 경우)
  - Query Parameters (있는 경우)
  - Body (있는 경우)
- **Response**:
  - HTTP Status
  - Body (Response 객체 필드 전체)
- **Error Cases**: 발생 가능한 **모든 오류 케이스**를 HTTP Status, Error Code, Error Message로 정리. 공통 에러 코드 참조 문서(`00. ErrorCodes.md`)가 있고 해당 오류가 포함된 경우, 중복 기재 대신 참조 링크로 대체한다.
- **Example**: Request Body 예시, 성공/실패 Response 예시 (Axios 예시 등 포함 가능)

#### 4-4. 생략 규칙

해당 항목이 없으면 아래 항목은 **생략**한다:
- Authority (권한 검증이 없는 경우)
- Path Variables (없는 경우)
- Query Parameters (없는 경우)
- Request Body (GET 등 Body가 없는 경우)
- Request Headers (공통 인증 헤더만 있고 별도 설명이 불필요한 경우)

---

### 5. 검토 및 최종 확인

문서 작성 후 다음을 검토한다:

- 소스코드에서 발생 가능한 모든 오류 케이스가 누락 없이 포함되었는지 확인
- 필드 타입, 필수 여부, 기본값, 설명이 정확한지 확인
- 참조 문서 링크가 올바른 상대 경로인지 확인
- 불명확한 사항이 남아 있다면 사용자에게 추가 확인 요청

---

## 업데이트/리팩토링 워크플로우

### U1. 대상 문서 및 소스코드 위치 확인

다음 두 가지를 입력받는다. 명시되지 않은 항목은 질문한다:

> "업데이트/리팩토링할 **기존 문서의 위치**를 알려주세요.  
> (예: `docs/api/03-ssl-certificate/`, `docs/api/03-ssl-certificate/create-ssl-certificate.md`)"

> "대응하는 **소스코드 위치**도 알려주세요.  
> (예: `src/main/java/com/example/controller/SslCertificateController.java`)"

- **업데이트**: 소스코드 위치가 필수다. 현재 소스코드를 기준으로 문서를 갱신한다.
- **리팩토링**: 소스코드 위치는 선택이다. 소스코드가 제공된 경우 내용 정확성도 함께 검증한다.

---

### U2. 기존 문서 전체 읽기

대상 문서(단건 또는 폴더 전체)를 읽고 현재 상태를 파악한다:

- 문서 구조, Front Matter, 각 섹션 내용 확인
- 참조 문서(`00-reference.md` 등)가 있다면 함께 읽는다.
- 도메인 폴더 내 다른 문서들도 확인하여 중복 여부 파악에 활용한다.

---

### U3. 소스코드와 기존 문서 비교 분석 (업데이트인 경우)

소스코드를 [신규 작성 워크플로우 2단계](#2-소스코드-전체-분석)와 동일하게 전체 분석한 후, 기존 문서와 비교하여 **변경된 항목**을 파악한다:

| 비교 항목 | 확인 내용 |
|---|---|
| 엔드포인트 | URL, HTTP 메서드 변경 여부 |
| Request | 필드 추가/삭제/타입 변경, 필수 여부 변경 |
| Response | 필드 추가/삭제/타입 변경 |
| Error Cases | 오류 코드/메시지 추가·삭제·변경 |
| 권한(Authority) | 권한 조건 변경 여부 |

변경 사항을 사용자에게 요약해서 보고한 후 진행한다:

> "다음 변경 사항을 확인했습니다. 문서에 반영할까요?
> - `expiresAt` 필드가 Response에 추가됨
> - `C4003` 오류 코드가 새로 추가됨
> - `name` 필드가 필수(TRUE)에서 선택(FALSE)으로 변경됨"

---

### U4. 리팩토링 항목 파악 (리팩토링인 경우)

기존 문서를 검토하여 개선이 필요한 항목을 파악하고 사용자에게 보고한다:

**구조 문제**
- 하나의 파일에 여러 API가 혼재하는 경우 → 파일 분리 제안
- 파일명이 `{NN}. {PascalCase}.md` 규칙을 따르지 않는 경우 → 파일명 변경 제안
- 폴더명이 `{숫자}. {PascalCase}` 규칙을 따르지 않는 경우 → 폴더명 변경 제안
- `_category_.json`이 없는 경우 → 생성 제안

**내용 문제**
- 오류 케이스 누락 (소스코드 제공 시 검증)
- 필드 설명 부재 또는 불명확
- Request/Response 형식이 현재 포맷 기준과 다른 경우

**중복 문제**
- 동일 도메인 폴더 내 여러 문서에서 공통 응답/오류 코드가 반복되는 경우 → 객체 참조 문서 분리 제안

> "다음 리팩토링 항목을 발견했습니다. 어떤 항목을 진행할까요?
> 1. 공통 오류 코드 3종이 4개 문서에 중복 → `00-error-codes.md` 분리
> 2. `create-ssl-cert.md` 파일명 → `create-ssl-certificate.md`로 변경
> 3. `list-ssl-certificate.md`에 오류 케이스 섹션 누락"

---

### U5. 변경/개선 사항 적용

사용자 확인을 받은 항목에 대해서만 문서를 수정한다.

- **업데이트**: 기존 문서 파일을 직접 수정한다. 파일 전체를 덮어쓰지 않고 변경된 섹션만 수정한다.
- **리팩토링**: 구조 변경(파일 분리, 파일명 변경 등)이 있을 경우 사용자에게 최종 확인 후 진행한다.
  - 객체 참조 문서 신규 생성 시, 다른 문서의 중복 내용을 참조 링크로 교체한다.

---

### U6. 검토 및 최종 확인

- 수정된 문서가 [api-docs-format.md](./api-docs-format.md) 형식을 준수하는지 확인
- 참조 문서 링크가 올바른 상대 경로인지 확인
- 소스코드 기준으로 누락된 항목이 없는지 최종 검토
- 불명확한 사항이 남아 있다면 사용자에게 추가 확인 요청
