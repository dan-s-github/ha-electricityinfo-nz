# Config-Flow Wireframe

```text
+--------------------------------------------------+
| Configure Electricity Price Sensor               |
+--------------------------------------------------+

Market Node
[ BRB0331 (Bream Bay, NI)              ▼ ]

Price Unit
(•) c/kWh
( ) NZD/kWh


====================================================
 LIVE PRICE
====================================================

[x] Current electricity price


====================================================
 FORECASTING
====================================================

[x] Enable forecast prices

Forecast Type
[x] Price-responsive (recommended)
[ ] Non-responsive

Forecast Horizons
[x] Day-ahead (PRSL / 24h)
[ ] Intraday updates (PRSS / 4h)

History Retention
( ) 6h
( ) 12h
(•) 24h


====================================================
 ACCOUNTING
====================================================

[x] Enable accounting sensors (interim settled prices)

History Retention
( ) 6h
( ) 12h
(•) 24h

Import meter entity (optional)
[ sensor.my_import_meter            ▼ ]

Export meter entity (optional)
[ (none)                            ▼ ]

Creates:
- settled price sensor
- import cost delta sensor (if import meter configured)
- export revenue delta sensor (if export meter configured)
- daily import cost sensor (if import meter configured)
- daily export revenue sensor (if export meter configured)

                [ CANCEL ] [ SUBMIT ]
```


## Entities Created

----------------------------------------------------

```
sensor.<node>_live_price

sensor.<node>_day_ahead_forecast
sensor.<node>_intraday_forecast

sensor.<node>_settled_price
sensor.<node>_import_cost
sensor.<node>_export_revenue
sensor.<node>_daily_import_cost
sensor.<node>_daily_export_revenue
```
