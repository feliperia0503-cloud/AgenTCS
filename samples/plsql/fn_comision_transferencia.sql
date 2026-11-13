-- ---------------------------------------------------------------------------
-- PROGRAMA SINTÉTICO PARA LA DEMO DE AGENTCS. SIN DATOS REALES.
-- Comisión de una transferencia interbancaria (resultado con 2 decimales).
--   * Monto nulo o <= 0: comisión 0.
--   * Canal APP con monto <= 500000: gratis.
--   * Tarifa por tramo: <= 1.000.000 -> 0.40 %; <= 10.000.000 -> 0.25 %;
--     mayor -> 0.15 %. Canal OFICINA suma 0.10 puntos a la tarifa.
--   * Comisión = ROUND(monto * tarifa, 2)  (redondeo mitad lejos de cero).
--   * Segmento PREMIUM: 50 % de descuento, TRUNCADO a 2 decimales.
--   * Tope de comisión antes de IVA: 25000.
--   * IVA 19 %: resultado = ROUND(comisión * 1.19, 2).
--   Canales distintos de APP/WEB/OFICINA se tratan como WEB.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_comision_transferencia (
    p_monto    IN NUMBER,
    p_canal    IN VARCHAR2,
    p_segmento IN VARCHAR2
) RETURN NUMBER
IS
    c_iva           CONSTANT NUMBER(4, 2)  := 0.19;
    c_tope          CONSTANT NUMBER(12, 2) := 25000;
    c_gratis_app    CONSTANT NUMBER(14, 2) := 500000;
    v_tarifa        NUMBER(7, 5);
    v_comision      NUMBER(12, 2);
BEGIN
    IF p_monto IS NULL OR p_monto <= 0 THEN
        RETURN 0;
    END IF;

    IF p_canal = 'APP' AND p_monto <= c_gratis_app THEN
        RETURN 0;
    END IF;

    IF p_monto <= 1000000 THEN
        v_tarifa := 0.004;
    ELSIF p_monto <= 10000000 THEN
        v_tarifa := 0.0025;
    ELSE
        v_tarifa := 0.0015;
    END IF;

    IF p_canal = 'OFICINA' THEN
        v_tarifa := v_tarifa + 0.001;
    END IF;

    v_comision := ROUND(p_monto * v_tarifa, 2);

    IF p_segmento = 'PREMIUM' THEN
        v_comision := TRUNC(v_comision * 0.5, 2);
    END IF;

    IF v_comision > c_tope THEN
        v_comision := c_tope;
    END IF;

    RETURN ROUND(v_comision * (1 + c_iva), 2);
END fn_comision_transferencia;
/
