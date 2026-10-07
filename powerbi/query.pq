// Create NeonHost and NeonDatabase text parameters in Power BI Desktop.
// Use native connector credential settings; do not put a password in M code.
let
    Source = PostgreSQL.Database(NeonHost, NeonDatabase, [CreateNavigationProperties=false]),
    Daily = Source{[Schema="talentpulse", Item="bi_daily_kpis"]}[Data],
    Typed = Table.TransformColumnTypes(Daily, {{"date", type date}})
in
    Typed
