-- Executar com a conta proprietária da tabela.
-- Impede que a mesma serventia oficial seja cadastrada mais de uma vez.
-- O CNS pode estar salvo formatado (10.864-7) ou somente com digitos (108647).
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_cartorios_cns_digits_unique
ON cartorios ((regexp_replace(cns, '[^0-9]', '', 'g')))
WHERE COALESCE(cns, '') <> '';
