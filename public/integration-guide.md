# Power BI and Adobe Analytics connections

The dedicated integration tabs use the same private workspace as uploads and model settings. The app keeps supplied credentials encrypted in Neon; only the workspace authorization token persists in browser storage. Connection checks make real requests. A saved URL or key is **configured**, and successful API verification is **verified**. Neither status guarantees every downstream report permission.

This project does not include StepStone credentials or production telemetry. Its base history is labelled synthetic. Uploaded rows, actual Adobe responses, and Microsoft-hosted reports retain separate provenance.

## Power BI: open a secure published report

1. Build and publish your report in your authorized Power BI workspace.
2. In the Power BI service, use **File → Embed report → Website or portal** and copy its secure URL. Open the **Power BI** tab in this lab, choose **Configure**, and save the HTTPS report URL.
3. Choose **Open Power BI**. Microsoft handles viewer authentication and permissions. A supported `reportEmbed` URL also enables **View here**, which loads the Microsoft-hosted iframe only after you choose it. Opening a frame is not treated as proof of authenticated report access.

Secure embedding requires viewer permissions. Microsoft currently specifies Pro or PPU for viewers unless both the report and its semantic model are on qualifying Premium or Fabric F64+ capacity. Browser privacy settings can require additional sign-in or block embedded authentication; open the report in its own tab when needed. [Microsoft secure embedding and licensing](https://learn.microsoft.com/en-us/power-bi/collaborate-share/service-embed-secure).

The optional Power BI REST access token is stored on the server and never passed into the iframe. A report’s own secure browser sign-in remains necessary. This application does not implement an automatic Microsoft OAuth redirect, service-principal embed-token generation, or an app-owns-data customer embedding system.

## Power BI: verify REST access and discover reports

For delegated REST authentication, register an organizational Microsoft Entra application, configure the relevant Power BI API permission, and obtain a valid token through your organization’s approved OAuth flow. [Microsoft app registration](https://learn.microsoft.com/en-us/power-bi/developer/embedded/register-app).

In **Configure**, save the access token and optional Power BI workspace/group UUID. **Save & verify** or **Verify & discover reports** calls the read-only reports endpoint. Its delegated scope can be `Report.Read.All`; the account must also have access to that workspace. Without a group ID, the connector queries the caller’s reports. Actual returned report names and validated links appear in the tab. [Power BI Get Reports In Group permissions](https://learn.microsoft.com/en-us/rest/api/power-bi/reports/get-reports-in-group).

A token can expire, and this app does not store a Microsoft refresh token. Replace the saved REST token when necessary. An empty token field preserves the previous encrypted value. Removing the private connector deletes that workspace’s saved configuration.

## Power BI: import this lab’s approved data

The native assets are [powerbi/query.pq](https://github.com/sohampatra3/talentpulse-analytics/blob/main/powerbi/query.pq), [powerbi/measures.dax](https://github.com/sohampatra3/talentpulse-analytics/blob/main/powerbi/measures.dax), and the views declared in [database/schema.sql](https://github.com/sohampatra3/talentpulse-analytics/blob/main/database/schema.sql). Use Power BI Desktop’s PostgreSQL connector with an authorized read-only role and encrypted transport. Enter database credentials in Power BI’s credential settings, rather than in the report query. Select an Import or DirectQuery workflow suitable for your report. [Microsoft PostgreSQL connector](https://learn.microsoft.com/en-us/power-query/connectors/postgresql).

For private uploads, export the selected dataset from the lab and import that approved file. The public analytics MCP endpoint exposes synthetic aggregates; it does not authorize Power BI to query arbitrary private uploads.

Publish the semantic model and configure source credentials and refresh in Power BI. Import models need refresh to incorporate source changes; opening or reloading this app’s iframe does not refresh the semantic model. [Microsoft data refresh](https://learn.microsoft.com/en-us/power-bi/connect-data/refresh-data).

Define and test row-level security in the semantic model, and assign appropriate role membership. RLS applies to Viewer users; workspace Admin, Member, and Contributor permissions have broader access. App URL filters are presentation choices and do not replace access controls. [Microsoft RLS guidance](https://learn.microsoft.com/en-us/fabric/security/service-admin-row-level-security).

Keep the experiment metric denominator consistent. The lab’s primary experiment compares exposed users in a fixed outcome window; its session funnel uses search sessions. Database views expose fractional rates, while the dashboard JSON exposes percentages. Preserve those definitions when importing measures.

## Adobe Analytics: prerequisites and authentication

Ask an Adobe Analytics administrator to assign the credential to product profiles with the necessary organization and report-suite access. Create a Developer Console project and add the Analytics API. Authentication alone does not grant data access. [Adobe Analytics API prerequisites](https://developer.adobe.com/analytics-apis/docs/2.0/guides/).

Open the **Adobe Analytics** tab and **Configure**. Choose one of the implemented methods:

- **Bearer token:** save your authorized client ID and access token. Replace the token when it expires.
- **OAuth server-to-server:** save client ID, client secret, and the exact comma-separated scopes shown in your Developer Console credential. The backend uses the `client_credentials` grant at Adobe IMS, caches tokens until shortly before expiry, and regenerates them when needed. Access is governed by the credential’s assigned product profiles. [Adobe server-to-server authentication](https://developer.adobe.com/developer-console/docs/guides/authentication/ServerToServerAuthentication/).

Save the actual global company ID and report-suite ID. REST **Save & verify** performs Adobe company discovery. Success verifies this API request; a report request can still fail if that report suite or metric is unavailable to the credential.

## Adobe Analytics: REST report workflow

Choose **REST**, then **Build an Adobe report**:

1. Set the inclusive date window. The adapter converts the end date to the next exclusive midnight, using the report-suite timezone.
2. Choose a real dimension ID, such as `variables/daterangeday`, and actual comma-separated metric IDs, such as `metrics/visits, metrics/pageviews`.
3. Add an authorized Adobe segment ID when you need a role, device, or experiment cohort.
4. Select **Fetch actual report**. The app submits `POST /api/{company}/reports` and displays the returned totals, up to 50 rows, a selectable-metric chart, response page information, and fetch provenance. Empty or failed responses remain empty or failed.

Adobe’s Reports API supports request-defined dimensions, metrics, date filters, and pagination; it returns data structures rather than visualizations. The lab renders the chart from those returned values. [Adobe Reporting API](https://developer.adobe.com/analytics-apis/docs/2.0/guides/endpoints/reports/).

## Adobe Analytics: official MCP workflow

Choose **MCP** and use the documented endpoint `https://aa-mcp.adobe.io/mcp`. The credential’s product profile must contain **MCP Access**, in addition to the Analytics permissions required for the request. [Adobe MCP prerequisites](https://developer.adobe.com/analytics-mcp/docs/guides/).

Save your IMS organization ID and global company ID. The server supplies the authorized bearer token, client ID, organization header, and company header; it initializes Streamable HTTP and discovers actual tools. OAuth server-to-server token generation is supported. [Adobe MCP OAuth headers and renewal](https://developer.adobe.com/analytics-mcp/docs/guides/oauth).

**Fetch actual report** invokes the documented read-only `runReport` tool using your dimension, metric IDs, window, and optional segment. The raw returned tool content is shown as external evidence. The app does not guess a numeric chart when remote tool content is unstructured. This connector uses reporting and discovery tools; it does not create segments or projects. [Adobe MCP tool reference](https://developer.adobe.com/analytics-mcp/docs/aa/reference).

## Comparing roles and search experiments

Map your own job role, assignment, application start, and application completion events to the actual Adobe dimensions and metrics. The app cannot know an organization’s custom eVars or event IDs. Use an existing segment to retrieve each cohort, inspect its denominator, and record the mapping alongside the question being investigated.

Fetched Adobe evidence is not automatically joined to private uploaded user identities or synthetic outcomes. Role comparisons remain observational unless a valid user-randomized assignment and outcome window are independently established. A higher segment count does not supply causal attribution or statistical significance. The lab’s role explanations preserve this distinction.

## Troubleshooting

| Symptom                          | What to check                                                                                                                                      |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| Settings show configured         | Save & verify performs the actual supported connection check. A URL alone does not prove authentication.                                           |
| Power BI token check fails       | Token expiry, correct Power BI API audience, delegated scope, workspace UUID, and caller access.                                                   |
| Power BI sign-in or blank frame  | Open the validated report in its own tab; review browser pop-up/cookie settings and Microsoft report permissions.                                  |
| Power BI values are stale        | Review source credentials and semantic-model refresh in Power BI.                                                                                  |
| Adobe unauthorized/rejected      | Token expiry, credential product profiles, organization/company IDs, report-suite access, and exact component IDs.                                 |
| Adobe MCP fails while REST works | Confirm MCP Access and the IMS organization/company headers, then retry verification.                                                              |
| Empty Adobe report               | Review the report-suite timezone, selected dates, segment filters, and whether that dimension has data.                                            |
| Private workspace loading fails  | Retry the current selection. Health liveness and actual database connectivity are separate checks; provider/report requests have bounded timeouts. |

No organization-specific account is silently assumed. Each tab retains explicit configuration and verification states until the user supplies an authorized connection.
