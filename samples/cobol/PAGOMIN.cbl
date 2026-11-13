       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAGOMIN.
      *----------------------------------------------------------------
      * PROGRAMA SINTETICO PARA LA DEMO DE AGENTCS. SIN DATOS REALES.
      * PAGO MINIMO MENSUAL DE UNA TARJETA DE CREDITO.
      * - INTERES DEL MES: SALDO * 2.15 %, REDONDEADO A 2 DECIMALES.
      * - PAGO BASE: 5 % DEL SALDO, TRUNCADO (SIN ROUNDED).
      * - SE SUMAN INTERES Y CUOTA DE MANEJO FIJA (12.50).
      * - PISO DE 50.00; TECHO = SALDO + INTERES + CUOTA.
      * - MAS DE 30 DIAS DE ATRASO: +10 % DEL SALDO (TRUNCADO).
      * - MAS DE 90 DIAS DE ATRASO: SE EXIGE EL TOTAL (TECHO).
      * ESTADO: A = AL DIA (SIN SALDO), N = NORMAL, M = MORA,
      *         J = COBRO JURIDICO.
      *----------------------------------------------------------------
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-PCT-MINIMO          PIC V99       VALUE .05.
       01  WS-PCT-MORA            PIC V99       VALUE .10.
       01  WS-TASA-MENSUAL        PIC V9(4)     VALUE .0215.
       01  WS-CUOTA-MANEJO        PIC 9(3)V99   VALUE 12.50.
       01  WS-PISO                PIC 9(5)V99   VALUE 50.00.
       01  WS-TECHO               PIC S9(9)V99  VALUE ZERO.
       01  WS-RECARGO-MORA        PIC S9(9)V99  VALUE ZERO.
       LINKAGE SECTION.
       01  LK-ENTRADA.
           05  LK-SALDO           PIC S9(9)V99.
           05  LK-DIAS-ATRASO     PIC 9(3).
       01  LK-SALIDA.
           05  LK-INTERES-MES     PIC S9(7)V99.
           05  LK-PAGO-MINIMO     PIC S9(9)V99.
           05  LK-ESTADO          PIC X(1).
       PROCEDURE DIVISION USING LK-ENTRADA LK-SALIDA.
       0000-PRINCIPAL.
           IF LK-SALDO NOT > ZERO
              MOVE ZERO TO LK-INTERES-MES
              MOVE ZERO TO LK-PAGO-MINIMO
              MOVE "A" TO LK-ESTADO
           ELSE
              PERFORM 1000-PAGO-BASE
              PERFORM 2000-APLICAR-ATRASO
              PERFORM 3000-APLICAR-LIMITES
           END-IF
           GOBACK.
       1000-PAGO-BASE.
           MOVE "N" TO LK-ESTADO
           COMPUTE LK-INTERES-MES ROUNDED = LK-SALDO * WS-TASA-MENSUAL
           COMPUTE LK-PAGO-MINIMO = LK-SALDO * WS-PCT-MINIMO
           ADD LK-INTERES-MES WS-CUOTA-MANEJO TO LK-PAGO-MINIMO
           COMPUTE WS-TECHO =
                   LK-SALDO + LK-INTERES-MES + WS-CUOTA-MANEJO.
       2000-APLICAR-ATRASO.
           IF LK-DIAS-ATRASO > 90
              MOVE "J" TO LK-ESTADO
              MOVE WS-TECHO TO LK-PAGO-MINIMO
           ELSE
              IF LK-DIAS-ATRASO > 30
                 MOVE "M" TO LK-ESTADO
                 COMPUTE WS-RECARGO-MORA = LK-SALDO * WS-PCT-MORA
                 ADD WS-RECARGO-MORA TO LK-PAGO-MINIMO
              END-IF
           END-IF.
       3000-APLICAR-LIMITES.
           IF LK-PAGO-MINIMO < WS-PISO
              MOVE WS-PISO TO LK-PAGO-MINIMO
           END-IF
           IF LK-PAGO-MINIMO > WS-TECHO
              MOVE WS-TECHO TO LK-PAGO-MINIMO
           END-IF.
