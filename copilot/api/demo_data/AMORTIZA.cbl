       IDENTIFICATION DIVISION.
       PROGRAM-ID. AMORTIZA.
      * Tabla de amortizacion francesa (cuota fija).
      * DATOS SINTETICOS - MODO DEMO DE AGENTCS.
      * Conexion de prueba: PASSWORD=Demo#2024! (debe enmascararse)
       ENVIRONMENT DIVISION.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-ENTRADA.
           05  WS-MONTO          PIC S9(9)V99 COMP-3.
           05  WS-TASA-ANUAL     PIC S9(3)V99 COMP-3.
           05  WS-PLAZO          PIC 9(3).
       01  WS-CALCULO.
           05  WS-TASA-MES       PIC S9(1)V9(8) COMP-3.
           05  WS-FACTOR         PIC S9(5)V9(8) COMP-3.
           05  WS-CUOTA          PIC S9(9)V99 COMP-3.
           05  WS-INTERES        PIC S9(9)V99 COMP-3.
           05  WS-CAPITAL        PIC S9(9)V99 COMP-3.
           05  WS-SALDO          PIC S9(9)V99 COMP-3.
           05  WS-I              PIC 9(3).
       01  WS-COD-ERROR          PIC X(3) VALUE SPACES.
       PROCEDURE DIVISION.
       0000-PRINCIPAL.
           PERFORM 1000-VALIDAR THRU 1000-VALIDAR-EXIT
           IF WS-COD-ERROR NOT = SPACES
              DISPLAY 'ERROR;' WS-COD-ERROR
              STOP RUN
           END-IF
           PERFORM 2000-AJUSTAR-TASA
           PERFORM 3000-CALCULAR-CUOTA
           PERFORM 4000-GENERAR-TABLA
           STOP RUN.
       1000-VALIDAR.
           IF WS-MONTO NOT > 0
              MOVE 'E01' TO WS-COD-ERROR
              GO TO 1000-VALIDAR-EXIT
           END-IF
           IF WS-PLAZO < 1 OR WS-PLAZO > 360
              MOVE 'E02' TO WS-COD-ERROR
           END-IF.
       1000-VALIDAR-EXIT.
           EXIT.
       2000-AJUSTAR-TASA.
           IF WS-MONTO >= 50000000
              SUBTRACT 0.50 FROM WS-TASA-ANUAL
           END-IF.
       3000-CALCULAR-CUOTA.
           COMPUTE WS-TASA-MES = WS-TASA-ANUAL / 1200
           COMPUTE WS-FACTOR = (1 + WS-TASA-MES) ** WS-PLAZO
           COMPUTE WS-CUOTA ROUNDED =
               WS-MONTO * WS-TASA-MES * WS-FACTOR / (WS-FACTOR - 1).
       4000-GENERAR-TABLA.
           MOVE WS-MONTO TO WS-SALDO
           PERFORM VARYING WS-I FROM 1 BY 1 UNTIL WS-I > WS-PLAZO
              COMPUTE WS-INTERES = WS-SALDO * WS-TASA-MES
              COMPUTE WS-CAPITAL = WS-CUOTA - WS-INTERES
              COMPUTE WS-SALDO = WS-SALDO - WS-CAPITAL
              DISPLAY WS-I ';' WS-CUOTA ';' WS-INTERES ';'
                      WS-CAPITAL ';' WS-SALDO
           END-PERFORM.
