# Logical Vertical Spacing

Separate distinct logical steps inside a method with blank lines so the execution flow is easy to scan.

Use blank lines between preparation, value serialization, request construction, external calls, return statements, and error handling when they represent different steps.

Also apply the same principle inside `try`, `catch`, `if`, `for`, and similar blocks: add vertical spacing when a new logical step begins.

Do not insert blank lines inside fluent chains, builder chains, or tightly related declarations that should be read as one expression.

Prefer this:

```java
@Override
public T save(String companyId, T document) {

    createIndexIfAbsent(companyId);
    IndexNames names = names(companyId);

    try {

        String json = objectMapper.writeValueAsString(document);
        IndexRequest request = new IndexRequest(names.writeAlias())
                .id(document.getId())
                .source(json, XContentType.JSON)
                .setRefreshPolicy(properties.defaultRefreshPolicy());

        clientGateway.index(request);

        return document;

    } catch (Exception e) {

        throw new IllegalStateException("Failed to save Elasticsearch document: " + document.getId(), e);

    }
}
```
