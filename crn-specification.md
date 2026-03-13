# Compact Resource Notation (CRN) — Specification v0.1

## 1. Overview

Compact Resource Notation (CRN) is a text-based format for representing Web resources in a token-efficient, LLM-readable form.
It serves as a unified intermediate representation that can be derived from HTML, RDF (Turtle, JSON-LD), and other Web data formats.

CRN separates a resource into four concerns:
- **Identity** (header): where the agent is
- **Content**: what the resource says (prose)
- **Properties**: structured data about the resource (literal values)
- **Links**: where the agent can go (dereferenceable URIs)

## 2. Design Principles

1. **Token efficiency**: URIs are prefix-compressed. Text references links by short IDs, not inline URIs. No structural syntax overhead (no tags, braces, or brackets beyond what is necessary).
2. **Content-link separation**: Informational content is separated from actionable navigation options. The agent can scan the link table without parsing prose.
3. **Line-oriented**: Each line is a self-contained unit of information. This enables context compression by dropping lines, not fragments.
4. **Section ordering is fixed**: Header → Content → Properties → Links → Forms. Under context pressure, later sections can be truncated while preserving identity and content.
5. **Graceful degradation**: All sections except `@resource` are optional. Missing sections are omitted, not empty.
6. **Bidirectional**: CRN can be translated to and from HTML and RDF without loss of navigational information.

## 3. Document Structure

A CRN document consists of a **header block** followed by zero or more **sections**.

```
<header>
<content-section>?
<properties-section>?
<links-section>?
<forms-section>?
```

Sections MUST appear in the order specified above.
Blank lines between sections are permitted for readability.

## 4. Header Block

The header block consists of one or more header fields, each on its own line.
Header fields start with `@`.

### 4.1 @resource (REQUIRED)

The URI of the current resource. This is the only required field.

```
@resource <absolute-URI>
```

The URI MUST be absolute. Angle brackets are required.

Example:
```
@resource <http://dbpedia.org/resource/Berlin>
```

### 4.2 @label (RECOMMENDED)

A human-readable label for the resource.

```
@label "text"
```

The value MUST be enclosed in double quotes.
Derived from: `rdfs:label` (RDF), `<title>` (HTML), or `<h1>` (HTML).

Example:
```
@label "Berlin"
```

### 4.3 @source

The media type of the original representation from which the CRN was derived.

```
@source media-type
```

Example:
```
@source text/turtle
```

Valid values include: `text/html`, `text/turtle`, `application/ld+json`, `application/json`, or any registered IANA media type.

### 4.4 @type

The type(s) of the resource. Multiple types are comma-separated.

```
@type type1, type2, ...
```

Types may use prefixed names (if a prefix is declared) or full URIs in angle brackets.

Example:
```
@type dbo:City, dbo:PopulatedPlace
```

### 4.5 @prefix

Declares a prefix for URI compression. Zero or more prefix declarations are allowed.

```
@prefix short: <base-URI>
```

The prefix name consists of alphanumeric characters and MUST end with a colon in the declaration.
The base URI MUST be enclosed in angle brackets.

Examples:
```
@prefix dbr: <http://dbpedia.org/resource/>
@prefix dbo: <http://dbpedia.org/ontology/>
@prefix w: <https://en.wikipedia.org/wiki/>
```

A prefixed URI `short:local-name` expands to `<base-URI>` + `local-name`.

Example: Given the prefix above, `dbr:Berlin` expands to `<http://dbpedia.org/resource/Berlin>`.

**Prefix selection heuristic**: A converter SHOULD declare a prefix when a URI base occurs 3 or more times in the document. The prefix name SHOULD be short (1–4 characters).

## 5. Content Section

```
== content ==
```

The content section contains free-form text describing the resource.
It begins with the section delimiter `== content ==` on its own line.
The section ends when the next section delimiter is encountered, or at end of document.

### 5.1 Inline References

Text MAY reference entries in the links table using the notation `[id]`, where `id` is a positive integer matching a link entry.

```
Berlin is the capital of Germany [1] and a member state of the European Union [2].
```

Rules:
- A reference `[id]` MUST correspond to an entry in the links section.
- The same `[id]` MAY appear multiple times in the content.
- Not all links need to be referenced in the content. Links that are not contextually embedded in prose (e.g., sidebar links, related-resource links) appear only in the links table.
- Literal square brackets in text MUST be escaped as `\[` and `\]`.

### 5.2 Paragraphs

Paragraphs are separated by blank lines. No markup is used for formatting.
The content section contains plain text only.

### 5.3 Omission

If the source representation has no textual content (e.g., a pure RDF resource with no `rdfs:comment` or `dbo:abstract`), the content section is omitted entirely.

## 6. Properties Section

```
== properties ==
```

The properties section contains structured, non-dereferenceable data about the resource as key-value pairs.

### 6.1 Syntax

Each property is on its own line:

```
key: value
```

- **key**: A property name. May be a prefixed name (e.g., `dbo:populationTotal`) or a plain name (e.g., `population`).
- **value**: A text value extending to the end of the line. No quotes required. No type annotations.
- The separator is a colon followed by a space (`: `).

### 6.2 Multi-valued Properties

When a property has multiple values, each value appears on a separate line with the same key:

```
language: German
language: English
language: Turkish
```

### 6.3 Nested Structures

Blank nodes or nested structures (e.g., an address with sub-properties) are flattened using dot notation:

```
address.city: Berlin
address.postalCode: 10115
address.country: Germany
```

### 6.4 Units and Datatypes

Units are included inline with the value. Datatype annotations from RDF (e.g., `^^xsd:integer`) are dropped. The value is presented in its most readable form.

```
population: 3748148
area: 891.7 km²
elevation: 34 m
```

### 6.5 Language Tags

If language is relevant, annotate the key with a language tag in parentheses:

```
label (en): Berlin
label (de): Berlin
label (fr): Berlin
```

If the document operates in a single language context, language tags MAY be omitted.

### 6.6 Omission

If the source representation has no literal-valued properties, the properties section is omitted entirely.

## 7. Links Section

```
== links ==
```

The links section lists all dereferenceable URIs discovered in the representation.
This is the primary navigation interface for the agent.

### 7.1 Syntax

Each link is on its own line:

```
[id] relationship "label" uri-ref
```

- **id**: A positive integer. IDs MUST be unique within the document. IDs SHOULD be assigned sequentially starting from 1.
- **relationship**: The type of relationship between the current resource and the target. May be a prefixed name (e.g., `dbo:country`), a plain name (e.g., `href`), or a full URI in angle brackets. See Section 7.3 for defaults.
- **label**: A human-readable label for the target resource, enclosed in double quotes. See Section 7.4 for derivation rules.
- **uri-ref**: The dereferenceable URI of the target. May be a prefixed URI (e.g., `dbr:Germany`) or a full URI in angle brackets (e.g., `<https://en.wikipedia.org/wiki/Germany>`).

Example:
```
[1] dbo:country "Germany" dbr:Germany
[2] dbo:leaderName "Kai Wegner" dbr:Kai_Wegner
[3] href "European Union" w:European_Union
```

### 7.2 Ordering

Links SHOULD be ordered as follows:
1. Links referenced in the content section, in order of first appearance of their `[id]`.
2. Remaining links, grouped by relationship type.

This ensures that contextually relevant links appear first.

### 7.3 Default Relationship Types

When the source does not provide an explicit relationship type:
- HTML `<a href>` without `rel` attribute: use `href`
- HTML `<a>` with `rel` attribute: use the `rel` value (e.g., `author`, `nofollow`)
- HTML `<link>` elements: use the `rel` value
- RDF triples: use the predicate URI (prefixed or full)

### 7.4 Label Derivation

The label MUST be provided for every link. Converters derive labels in the following priority order:

1. **RDF**: `rdfs:label` of the target resource (if available in the current representation). Fall back to the local name of the URI (e.g., `Berlin` from `dbr:Berlin`, `Kai_Wegner` from `dbr:Kai_Wegner` with underscores replaced by spaces).
2. **HTML**: Anchor text of the `<a>` element. If empty, use the `title` attribute. Fall back to the local path segment of the URL.

### 7.5 Omission

If the source representation contains no dereferenceable URIs, the links section is omitted entirely.
This should be rare for Web resources but may occur for leaf nodes.

## 8. Forms Section

```
== forms ==
```

The forms section describes parameterized interactions available at the current resource.
This section is OPTIONAL and intended for future use with HTML forms, Hydra operations, and WoT interaction affordances.

### 8.1 Syntax

Each form is on its own line:

```
[fid] METHOD "label" uri-ref {param1: type, param2: type, ...}
```

- **fid**: A form identifier, prefixed with `f` (e.g., `f1`, `f2`). Unique within the document.
- **METHOD**: The HTTP method. One of: `GET`, `POST`, `PUT`, `DELETE`.
- **label**: A human-readable label for the action, enclosed in double quotes.
- **uri-ref**: The target URI (action endpoint). Same format as in links.
- **parameters**: A comma-separated list of `name: type` pairs enclosed in braces.

Parameter types:
- `text` — free text input
- `number` — numeric input
- `select(a|b|c)` — enumerated values
- `hidden(value)` — pre-filled value not requiring agent input
- `uri` — a URI value

Example:
```
[f1] GET "Search" <https://en.wikipedia.org/w/index.php> {search: text, ns: hidden(0)}
[f2] POST "Update" <https://api.example.org/resource> {name: text, value: text}
```

### 8.2 Derivation

- **HTML**: From `<form>` elements. Method from `method` attribute, action URI from `action` attribute, parameters from `<input>`, `<select>`, `<textarea>` elements.
- **Hydra**: From `hydra:Operation`. Method from `hydra:method`, parameters from `hydra:expects`.
- **WoT TD**: From interaction affordances (`PropertyAffordance`, `ActionAffordance`, `EventAffordance`). Each affordance's `forms` array provides the protocol binding.

### 8.3 Omission

If the source representation contains no forms or interaction affordances, the forms section is omitted entirely.

## 9. URI Handling

### 9.1 Absolute URIs

All URIs in CRN MUST be absolute. Relative URIs MUST be resolved against the `@resource` URI before encoding.

### 9.2 Prefixed URIs

A prefixed URI has the form `prefix:local-name`.
It expands to the concatenation of the prefix's base URI and the local name.

The local name MAY contain: alphanumeric characters, `-`, `_`, `.`, `~`, `(`, `)`.
Characters outside this set MUST be percent-encoded.

### 9.3 Full URIs

Full URIs are enclosed in angle brackets: `<https://example.org/path>`.
Used when no declared prefix matches the URI base.

### 9.4 URI Equality

Two URI references are equal if and only if their expanded forms are character-by-character identical after prefix expansion.

## 10. Encoding

### 10.1 Character Encoding

CRN documents MUST be encoded in UTF-8.

### 10.2 Line Endings

Lines are terminated by `\n` (LF) or `\r\n` (CRLF).

### 10.3 Escaping

The following escape sequences are recognized:
- `\"` — literal double quote within a quoted string
- `\[` — literal opening square bracket in content (not an inline reference)
- `\]` — literal closing square bracket in content
- `\\` — literal backslash

### 10.4 Maximum Line Length

No hard limit. However, converters SHOULD aim for lines under 200 characters for readability.

## 11. Translation Rules

### 11.1 HTML → CRN

| HTML element | CRN mapping |
|---|---|
| `<title>` or `<h1>` | `@label` |
| Page URL | `@resource` |
| `<meta>` with schema.org types | `@type` |
| Main content (`<article>`, `<main>`, or `<body>` after boilerplate removal) | `== content ==` |
| `<a href="...">text</a>` in content | Inline reference `[id]` in content + entry in `== links ==` |
| `<a href="...">` outside main content (nav, sidebar, footer) | Entry in `== links ==` only (no inline reference) |
| Infobox / `<dl>` / `<table>` key-value pairs | `== properties ==` |
| `<form>` elements | `== forms ==` |
| CSS, JavaScript, comments, hidden elements | Discarded |

### 11.2 RDF → CRN

| RDF construct | CRN mapping |
|---|---|
| Subject URI | `@resource` |
| `rdfs:label` of subject | `@label` |
| `rdf:type` | `@type` |
| `dbo:abstract` or `rdfs:comment` | `== content ==` |
| Triples with literal objects | `== properties ==` (key = predicate, value = literal) |
| Triples with URI objects | `== links ==` (relationship = predicate, uri-ref = object URI) |
| Blank node objects | Flatten into `== properties ==` with dot notation |
| Common URI bases (3+ occurrences) | `@prefix` declaration |

### 11.3 CRN → HTML

| CRN element | HTML mapping |
|---|---|
| `@resource` | `<link rel="canonical" href="...">` |
| `@label` | `<title>` and `<h1>` |
| `== content ==` | `<article>` with `<p>` tags; `[id]` replaced by `<a href="uri">label</a>` from links table |
| `== properties ==` | `<dl>` definition list or `<table>` |
| `== links ==` (not referenced in content) | `<nav><ul><li><a>` list |
| `== forms ==` | `<form>` elements with `<input>` fields |

### 11.4 CRN → RDF (Turtle)

| CRN element | RDF mapping |
|---|---|
| `@resource` | Subject URI for all triples |
| `@label` | `rdfs:label` triple |
| `@type` | `rdf:type` triple(s) |
| `@prefix` | Turtle `@prefix` declaration |
| `== content ==` | `dbo:abstract` triple (full text as literal) |
| `== properties ==` | Datatype property triples (`subject predicate "value"`) |
| `== links ==` | Object property triples (`subject relationship target-URI`) |

## 12. Media Type and File Extension

- Media type: `text/crn` (provisional)
- File extension: `.crn`

## 13. Complete Examples

### 13.1 From Wikipedia HTML

```
@resource <https://en.wikipedia.org/wiki/Berlin>
@label "Berlin"
@source text/html
@prefix w: <https://en.wikipedia.org/wiki/>

== content ==
Berlin is the capital and largest city of Germany [1].
It has a population of 3,748,148, making it the most populous city
in the European Union [2].
The city is situated on the River Spree [3] in northeastern Germany.

Berlin was the capital of Prussia [4] and later the German Empire [5].
After World War II [6], the city was divided.
The Berlin Wall [7] separated East and West Berlin from 1961 to 1989.

== properties ==
population: 3748148
area: 891.7 km²
elevation: 34 m
country: Germany
mayor: Kai Wegner

== links ==
[1] href "Germany" w:Germany
[2] href "European Union" w:European_Union
[3] href "Spree" w:Spree_(river)
[4] href "Prussia" w:Prussia
[5] href "German Empire" w:German_Empire
[6] href "World War II" w:World_War_II
[7] href "Berlin Wall" w:Berlin_Wall
[8] href "Brandenburg" w:Brandenburg
[9] href "Weimar Republic" w:Weimar_Republic
[10] href "Cold War" w:Cold_War
[11] href "Reichstag" w:Reichstag_building
```

### 13.2 From DBpedia Turtle

```
@resource <http://dbpedia.org/resource/Berlin>
@label "Berlin"
@source text/turtle
@type dbo:City, dbo:PopulatedPlace
@prefix dbr: <http://dbpedia.org/resource/>
@prefix dbo: <http://dbpedia.org/ontology/>

== content ==
Berlin is the capital and largest city of Germany [1] and one of the
sixteen states of Germany [2].

== properties ==
dbo:populationTotal: 3748148
dbo:areaTotal: 891.7 km²
dbo:elevation: 34.0 m
dbo:postalCode: 10115-14199
dbo:foundingDate: 1237

== links ==
[1] dbo:country "Germany" dbr:Germany
[2] dbo:federalState "Brandenburg" dbr:Brandenburg
[3] dbo:leaderName "Kai Wegner" dbr:Kai_Wegner
[4] dbo:river "Spree" dbr:Spree_(river)
[5] dbo:isPartOf "European Union" dbr:European_Union
[6] dbo:timeZone "Central European Time" dbr:Central_European_Time
[7] dbo:demonym "Berliner" dbr:Berliner
[8] dbo:subdivision "Mitte" dbr:Mitte_(locality)
[9] dbo:subdivision "Kreuzberg" dbr:Kreuzberg
```

### 13.3 With Forms (HTML search page)

```
@resource <https://en.wikipedia.org/wiki/Main_Page>
@label "Wikipedia - Main Page"
@source text/html
@prefix w: <https://en.wikipedia.org/wiki/>

== content ==
Welcome to Wikipedia, the free encyclopedia with 6,900,000+ articles.

== links ==
[1] href "Featured article" w:Wikipedia:Featured_articles
[2] href "Random article" w:Special:Random
[3] href "Community portal" w:Wikipedia:Community_portal

== forms ==
[f1] GET "Search Wikipedia" <https://en.wikipedia.org/w/index.php> {search: text, fulltext: hidden(1)}
```

## 14. Token Efficiency Analysis

Approximate token counts for the Berlin resource across formats:

| Format | Tokens (est.) | Ratio vs CRN |
|---|---|---|
| Raw Wikipedia HTML | ~15,000 | 30x |
| Wikipedia HTML + Markdown cleaning | ~3,000 | 6x |
| Raw DBpedia Turtle | ~3,000 | 6x |
| DBpedia Turtle + light cleaning | ~2,000 | 4x |
| Raw DBpedia JSON-LD | ~5,000 | 10x |
| **CRN (from either source)** | **~500** | **1x** |

Token savings come from:
- URI prefix compression (~8 tokens saved per prefixed URI)
- Removal of syntactic overhead (HTML tags, JSON structure, Turtle punctuation)
- Inline references `[id]` instead of embedded URIs in prose (~10 tokens saved per link in text)
- Deduplication (each URI appears exactly once, in the links table)
