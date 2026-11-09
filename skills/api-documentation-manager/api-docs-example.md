---
sidebar_position: 1
title: SSL 인증서 등록
tags:
  - SslCertificate
  - ExampleProduct
---
# SSL 인증서 등록

### 해당 회사에서 사용할 SSL 인증서를 등록한다.

- 관리자는 서비스에서 사용할 SSL 인증서를 등록할 수 있다.
- PEM 형식의 인증서만 지원한다.
- 인증서 이름을 입력하지 않으면 Subject CN에서 자동 추출한다.
- 인증서 만료일(expiresAt)은 PEM 파싱을 통해 자동 설정된다.

## Request

### URL

> POST /api/ssl-certifications

### Headers

| Key           | Value                 |
|---------------|-----------------------|
| Authorization | Security365 *JWT* 토큰 |
| Content-Type  | application/json      |

### Authority
| Privilege |
|-----------|
| MASTER    |
| ADMIN     |
---

### Body

| NAME           | TYPE          | REQUIRE | DESCRIPTION                                                  |
| -------------- | ------------- | ------- | ------------------------------------------------------------ |
| companyId      | UUID (String) | TRUE    | 회사 아이디 (토큰의 회사 아이디와 일치해야 함)               |
| name           | String        | FALSE   | 인증서 이름 (미입력 시 Subject CN에서 자동 추출)             |
| description    | String        | FALSE   | 인증서 설명                                                  |
| certificatePem | String        | TRUE    | PEM 형식의 인증서 내용                                       |
| isEnabled      | Boolean       | FALSE   | 활성화 여부 (기본값: true)                                   |

---

## Response

### Body

| NAME           | TYPE            | DESCRIPTION                          |
| -------------- | --------------- | ------------------------------------ |
| id             | UUID (String)   | SSL 인증서 아이디                    |
| companyId      | UUID (String)   | 회사 아이디                          |
| name           | String          | 인증서 이름                          |
| description    | String          | 인증서 설명                          |
| certificatePem | String          | PEM 형식의 인증서 내용               |
| expiresAt      | String          | 인증서 만료일 (ISO 8601)             |
| isEnabled      | Boolean         | 활성화 여부                          |
| createDate     | String          | 생성 일자 (ISO 8601)                 |
| modifyDate     | String          | 수정 일자 (ISO 8601)                 |

---

## Error Cases

| HTTP Status | Error Code | Error Message                                            |
| ----------- | ---------- | -------------------------------------------------------- |
| 400         | C4001      | companyId가 토큰의 회사 아이디와 일치하지 않음           |
| 400         | C4001      | 유효하지 않은 PEM 형식                                   |
| 400         | C4002      | companyId 누락                                           |
| 400         | C4002      | certificatePem 누락                                      |
| 403         | C4005      | MASTER 또는 ADMIN 권한 없음                              |
| 500         | C5001      | 서버 내부 오류                                           |

---

## Example

### Request Body

```json
{
    "companyId": "8e55f554-22a2-4f36-abe9-c12236ac0dac",
    "name": "ePrism SSL CA",
    "description": "사내 CA 인증서",
    "certificatePem": "-----BEGIN CERTIFICATE-----\nMIIDxTCCAq2gAwIBAgIJANX7yQ1GsPcpMA0GCSqGSIb3DQEBCwUAMHkxCzAJBgNV\n...\n-----END CERTIFICATE-----",
    "isEnabled": true
}
```

### Axios example

```javascript
var axios = require('axios');

var data = JSON.stringify({
    "companyId": "8e55f554-22a2-4f36-abe9-c12236ac0dac",
    "name": "ePrism SSL CA",
    "description": "사내 CA 인증서",
    "certificatePem": "-----BEGIN CERTIFICATE-----\nMIIDxTCCAq2gAwIBAgIJANX7yQ1GsPcpMA0GCSqGSIb3DQEBCwUAMHkxCzAJBgNV\n...\n-----END CERTIFICATE-----",
    "isEnabled": true
});

var config = {
  method: 'post',
  maxBodyLength: Infinity,
  url: 'https://api.example.com/api/ssl-certifications',
  headers: { 
    'Authorization': 'eyJ0eXAiOiJKV1QiLCJraWQiOiJCRGZPY3d5NC1m...', 
    'Content-Type': 'application/json'
  },
  data : data
};

axios(config)
.then(function (response) {
  console.log(JSON.stringify(response.data));
})
.catch(function (error) {
  console.log(error);
});
```

### Response: 200

```json
{
    "id": "3e2e4d33-bb87-4fb5-b6d4-ad5a1f2d6781",
    "companyId": "8e55f554-22a2-4f36-abe9-c12236ac0dac",
    "name": "ePrism SSL CA",
    "description": "사내 CA 인증서",
    "certificatePem": "-----BEGIN CERTIFICATE-----\nMIIDxTCCAq2gAwIBAgIJANX7yQ1GsPcpMA0GCSqGSIb3DQEBCwUAMHkxCzAJBgNV\n...\n-----END CERTIFICATE-----",
    "expiresAt": "2027-12-31T23:59:59",
    "isEnabled": true,
    "createDate": "2024-04-23T04:38:08.057633712",
    "modifyDate": "2024-04-23T04:38:08.057639131"
}
```

### Response: 400 (Invalid Company ID)

```json
{
    "status": 400,
    "error": "Bad Request",
    "message": "invalid company id: 8e55f554-22a2-4f36-abe9-c12236ac0dac"
}
```

### Response: 400 (Invalid PEM Format)

```json
{
    "status": 400,
    "error": "Bad Request",
    "message": "Invalid certificate PEM format"
}
```

---
