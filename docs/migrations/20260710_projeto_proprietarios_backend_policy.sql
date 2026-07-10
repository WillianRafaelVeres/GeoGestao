CREATE POLICY backend_all
    ON public.projeto_proprietarios
    FOR ALL
    TO geogestao_app
    USING (true)
    WITH CHECK (true);
