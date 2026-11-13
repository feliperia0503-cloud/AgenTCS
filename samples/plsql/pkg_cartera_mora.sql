-- ---------------------------------------------------------------------------
-- PROGRAMA SINTÉTICO PARA LA DEMO DE AGENTCS. SIN DATOS REALES.
-- Liquidación de interés de mora de un crédito (lee 2 tablas, actualiza 1).
--   * Crédito inexistente: ORA-20001 'CREDITO NO EXISTE'.
--   * Crédito castigado: ORA-20002 'CREDITO CASTIGADO'.
--   * Días de mora = fecha de corte - fecha de vencimiento; sin mora => 0.
--   * Interés = saldo * tasa anual / 360 * MIN(días, 180), asignado a NUMBER(14,2)
--     (la ASIGNACIÓN redondea mitad lejos de cero; no trunca).
--   * Descuento por segmento: PREMIUM 20 %, ORO 10 %, TRUNCADO a 2 decimales.
--   * Estado: > 180 días CASTIGADO; > 30 días MORA; si no, se conserva.
-- ---------------------------------------------------------------------------
CREATE TABLE clientes (
    cliente_id   NUMBER(10)    PRIMARY KEY,
    nombre       VARCHAR2(60),
    segmento     VARCHAR2(10)  NOT NULL
);

CREATE TABLE creditos (
    credito_id         NUMBER(10)    PRIMARY KEY,
    cliente_id         NUMBER(10)    NOT NULL REFERENCES clientes (cliente_id),
    saldo              NUMBER(14, 2) NOT NULL,
    tasa_mora_anual    NUMBER(7, 4)  NOT NULL,
    fecha_vencimiento  DATE          NOT NULL,
    estado             VARCHAR2(10)  DEFAULT 'VIGENTE' NOT NULL,
    interes_mora       NUMBER(14, 2) DEFAULT 0
);

CREATE OR REPLACE PACKAGE pkg_cartera AS
    c_dias_castigo CONSTANT PLS_INTEGER := 180;
    FUNCTION liquidar_mora (p_credito_id IN NUMBER, p_fecha_corte IN DATE) RETURN NUMBER;
END pkg_cartera;
/

CREATE OR REPLACE PACKAGE BODY pkg_cartera AS

    FUNCTION descuento_segmento (p_segmento IN VARCHAR2) RETURN NUMBER IS
    BEGIN
        RETURN CASE p_segmento WHEN 'PREMIUM' THEN 0.20 WHEN 'ORO' THEN 0.10 ELSE 0 END;
    END descuento_segmento;

    FUNCTION liquidar_mora (p_credito_id IN NUMBER, p_fecha_corte IN DATE) RETURN NUMBER IS
        v_saldo     creditos.saldo%TYPE;
        v_tasa      creditos.tasa_mora_anual%TYPE;
        v_vence     creditos.fecha_vencimiento%TYPE;
        v_estado    creditos.estado%TYPE;
        v_segmento  clientes.segmento%TYPE;
        v_dias      PLS_INTEGER;
        v_interes   NUMBER(14, 2);
    BEGIN
        SELECT c.saldo, c.tasa_mora_anual, c.fecha_vencimiento, c.estado, cl.segmento
          INTO v_saldo, v_tasa, v_vence, v_estado, v_segmento
          FROM creditos c
          JOIN clientes cl ON cl.cliente_id = c.cliente_id
         WHERE c.credito_id = p_credito_id;

        IF v_estado = 'CASTIGADO' THEN
            RAISE_APPLICATION_ERROR(-20002, 'CREDITO CASTIGADO');
        END IF;

        v_dias := TRUNC(p_fecha_corte) - TRUNC(v_vence);
        IF v_dias <= 0 THEN
            RETURN 0;
        END IF;

        v_interes := v_saldo * v_tasa / 360 * LEAST(v_dias, c_dias_castigo);
        v_interes := v_interes - TRUNC(v_interes * descuento_segmento(v_segmento), 2);

        UPDATE creditos
           SET interes_mora = v_interes,
               estado = CASE WHEN v_dias > c_dias_castigo THEN 'CASTIGADO'
                             WHEN v_dias > 30 THEN 'MORA'
                             ELSE estado END
         WHERE credito_id = p_credito_id;

        RETURN v_interes;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            RAISE_APPLICATION_ERROR(-20001, 'CREDITO NO EXISTE');
    END liquidar_mora;

END pkg_cartera;
/
