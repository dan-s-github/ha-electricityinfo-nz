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
 ACCOUNTING / ANALYTICS
====================================================

[x] Final settled prices

History Retention
( ) 6h
( ) 12h
(•) 24h

Creates:
- import cost sensors
- export revenue sensors
- arbitrage analytics

                [ CANCEL ] [ SUBMIT ]
```


## Entities Created

----------------------------------------------------

```
sensor.<node>_current_price

sensor.<node>_price_forecast_prsl
sensor.<node>_price_forecast_prss

sensor.<node>_final_price
```

