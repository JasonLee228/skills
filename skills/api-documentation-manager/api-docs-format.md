---
sidebar_position: 1
title: API 문서 제목
tags:
  - 태그1
  - 태그2
---

# API 제목

### 한 줄 요약 설명

- 주요 동작 설명 1
- 주요 동작 설명 2
- 주요 동작 설명 3

---

## Request

### URL

> METHOD /api/endpoint

### Headers

| Key           | Value                  |
|---------------|------------------------|
| Authorization | Security365 *JWT* 토큰 |
| Content-Type  | application/json       |

### Authority

| Privilege | Description      |
|-----------|------------------|
| MASTER    | 마스터 관리자    |
| ADMIN     | 일반 관리자      |

---

### Path Variables

| NAME | TYPE | REQUIRE | DESCRIPTION |
|------|------|---------|-------------|
| id   | UUID (String) | TRUE | 리소스 아이디 |

### Query Parameters

| NAME | TYPE | REQUIRE | DEFAULT | DESCRIPTION |
|------|------|---------|---------|-------------|
| page | Integer | FALSE | 0 | 페이지 번호 |
| size | Integer | FALSE | 20 | 페이지 크기 |

### Body

| NAME | TYPE | REQUIRE | DESCRIPTION |
|------|------|---------|-------------|
| fieldName | Type | TRUE/FALSE | 설명 |

---

## Response

### HTTP Status

| Status | Description |
|--------|-------------|
| 200    | 성공        |
| 201    | 생성 성공   |

### Body

| NAME | TYPE | DESCRIPTION |
|------|------|-------------|
| id   | UUID (String) | 리소스 아이디 |
| createDate | String | 생성 일자 (ISO 8601) |
| modifyDate | String | 수정 일자 (ISO 8601) |

---

## Error Cases

| HTTP Status | Error Code | Error Message |
|-------------|------------|---------------|
| 400 | C4001 | 설명 |
| 400 | C4002 | 필수 필드 누락 |
| 403 | C4005 | 권한 없음 |
| 404 | C4004 | 리소스 없음 |
| 500 | C5001 | 서버 내부 오류 |

---

## Example

### Axios example

```javascript
var axios = require('axios');

var config = {
  method: 'api http method',
  maxBodyLength: Infinity,
  url: 'https://api.example.com/API주소..',
  headers: { 
    'Authorization': 'eyJ0eXAiOiJKV1QiLCJraWQiOiJCRGZPY3d5NC1m...'
  }
};

axios(config)
.then(function (response) {
  console.log(JSON.stringify(response.data));
})
.catch(function (error) {
  console.log(error);
});
```

### Request Body

{
    "fieldName": "value"
}

### Response: 200

```json
{
    "id": "3e2e4d33-bb87-4fb5-b6d4-ad5a1f2d6781",
    "companyId": "8e55f554-22a2-4f36-abe9-c12236ac0dac",
    ...
}
```
