-- Arquitetura central de Pessoas e Representacoes
-- ==================================================
-- Este arquivo documenta o schema JA APLICADO no banco de producao do
-- GeoGestao (Supabase). Ele NAO e executado automaticamente contra producao.
--
-- Uso: e lido e executado apenas pelo bootstrap idempotente de banco LOCAL/DEV
-- (ver `bootstrap_pessoas_representacoes_schema()` em app.py, chamado somente
-- quando o operador roda `python app.py --init-db` ou define
-- GEOGESTAO_AUTO_INIT_DB=1 explicitamente). Nunca rode este arquivo direto
-- contra producao: o schema de producao ja foi migrado e este script existe
-- apenas para permitir que um banco novo (dev/teste) alcance o mesmo estado.
--
-- Toda instrucao aqui e idempotente (IF NOT EXISTS / CREATE OR REPLACE /
-- DROP TRIGGER IF EXISTS + CREATE TRIGGER / blocos DO com checagem em
-- pg_constraint), portanto rodar este arquivo de novo em um banco que ja o
-- tem aplicado e um no-op seguro.
--
-- O placeholder abaixo e substituido em runtime pelo valor da variavel de
-- ambiente GEOGESTAO_ASSINATURAS_APP_KEY. O valor real do segredo nunca fica
-- neste arquivo nem em nenhum outro arquivo versionado.
--   __ASSINATURAS_APP_KEY__
--
-- Pre-requisito: as tabelas legadas (clientes, pessoas_fisicas, pessoas_juridicas,
-- conjuges, procuradores, enderecos_proprietario) e a RPC antiga
-- `public.atualizar_qualificacao_proprietario` ja precisam existir antes de
-- rodar este arquivo -- elas fazem parte do bootstrap legado existente em
-- app.py e nao sao recriadas aqui.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS private;

-- ==================================================
-- 1. Tabelas centrais
-- ==================================================

CREATE TABLE IF NOT EXISTS public.pessoas_cadastro (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tipo_pessoa text NOT NULL DEFAULT 'PESSOA_FISICA',
    nome_exibicao text NOT NULL,
    nome_busca text NOT NULL DEFAULT '',
    documento text,
    documento_normalizado text NOT NULL DEFAULT '',
    ativo boolean NOT NULL DEFAULT true,
    origem text NOT NULL DEFAULT 'CADASTRO',
    criado_em timestamptz NOT NULL DEFAULT now(),
    atualizado_em timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.pessoas_fisicas_cadastro (
    pessoa_id uuid PRIMARY KEY REFERENCES public.pessoas_cadastro(id) ON DELETE CASCADE,
    sexo text,
    nome_completo text,
    estado_civil text,
    regime_casamento text,
    profissao_ocupacao text,
    nacionalidade text,
    rg text,
    orgao_expedidor_rg text,
    cpf text,
    nome_pai text,
    nome_mae text,
    data_nascimento text,
    uf_nascimento text,
    cidade_nascimento text,
    email text,
    telefone text,
    texto_adicional text,
    tipo_endereco text,
    logradouro text,
    uf text,
    cidade text,
    bairro text,
    cep text,
    numero text,
    complemento text,
    criado_em timestamptz NOT NULL DEFAULT now(),
    atualizado_em timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.pessoas_juridicas_cadastro (
    pessoa_id uuid PRIMARY KEY REFERENCES public.pessoas_cadastro(id) ON DELETE CASCADE,
    razao_social text,
    nome_fantasia text,
    cnpj text,
    email text,
    telefone text,
    tipo_endereco text,
    logradouro text,
    uf text,
    cidade text,
    bairro text,
    cep text,
    numero text,
    complemento text,
    criado_em timestamptz NOT NULL DEFAULT now(),
    atualizado_em timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.representacoes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    natureza text NOT NULL DEFAULT 'REPRESENTACAO',
    modo_atuacao text NOT NULL DEFAULT 'INDIVIDUAL',
    principal boolean NOT NULL DEFAULT false,
    ativo boolean NOT NULL DEFAULT true,
    documento_base text,
    referencia_documento text,
    escopo_poderes text,
    validade_inicio date,
    validade_fim date,
    observacoes text,
    origem text NOT NULL DEFAULT 'MANUAL',
    criado_em timestamptz NOT NULL DEFAULT now(),
    atualizado_em timestamptz NOT NULL DEFAULT now()
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'representacoes_modo_check') THEN
        ALTER TABLE public.representacoes
            ADD CONSTRAINT representacoes_modo_check
            CHECK (modo_atuacao = ANY (ARRAY['INDIVIDUAL', 'CONJUNTA', 'QUALQUER_UM']));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'representacoes_validade_check') THEN
        ALTER TABLE public.representacoes
            ADD CONSTRAINT representacoes_validade_check
            CHECK (validade_fim IS NULL OR validade_inicio IS NULL OR validade_fim >= validade_inicio);
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS public.representacao_representantes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    representacao_id uuid NOT NULL REFERENCES public.representacoes(id) ON DELETE CASCADE,
    pessoa_id uuid NOT NULL REFERENCES public.pessoas_cadastro(id),
    papel text NOT NULL DEFAULT 'PROCURADOR',
    principal boolean NOT NULL DEFAULT false,
    ordem integer NOT NULL DEFAULT 0,
    procurador_legado_id integer,
    criado_em timestamptz NOT NULL DEFAULT now(),
    atualizado_em timestamptz NOT NULL DEFAULT now()
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'representacao_representantes_unique') THEN
        ALTER TABLE public.representacao_representantes
            ADD CONSTRAINT representacao_representantes_unique UNIQUE (representacao_id, pessoa_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'representacao_representantes_procurador_legado_id_fkey') THEN
        ALTER TABLE public.representacao_representantes
            ADD CONSTRAINT representacao_representantes_procurador_legado_id_fkey
            FOREIGN KEY (procurador_legado_id) REFERENCES public.procuradores(id) ON DELETE SET NULL;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS public.representacao_representados (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    representacao_id uuid NOT NULL REFERENCES public.representacoes(id) ON DELETE CASCADE,
    cliente_id integer REFERENCES public.clientes(id) ON DELETE CASCADE,
    pessoa_id uuid REFERENCES public.pessoas_cadastro(id),
    criado_em timestamptz NOT NULL DEFAULT now()
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'representacao_representados_alvo_check') THEN
        ALTER TABLE public.representacao_representados
            ADD CONSTRAINT representacao_representados_alvo_check
            CHECK (
                (cliente_id IS NOT NULL AND pessoa_id IS NULL)
                OR (cliente_id IS NULL AND pessoa_id IS NOT NULL)
            );
    END IF;
END $$;

-- ==================================================
-- 2. Colunas novas nas tabelas legadas
-- ==================================================

ALTER TABLE public.clientes ADD COLUMN IF NOT EXISTS pessoa_id uuid REFERENCES public.pessoas_cadastro(id);
ALTER TABLE public.clientes ADD COLUMN IF NOT EXISTS condicao_juridica text NOT NULL DEFAULT 'NORMAL';
ALTER TABLE public.clientes ADD COLUMN IF NOT EXISTS nome_documental text;
ALTER TABLE public.pessoas_fisicas ADD COLUMN IF NOT EXISTS pessoa_id uuid REFERENCES public.pessoas_cadastro(id);
ALTER TABLE public.pessoas_juridicas ADD COLUMN IF NOT EXISTS pessoa_id uuid REFERENCES public.pessoas_cadastro(id);
ALTER TABLE public.conjuges ADD COLUMN IF NOT EXISTS pessoa_id uuid REFERENCES public.pessoas_cadastro(id);
ALTER TABLE public.procuradores ADD COLUMN IF NOT EXISTS pessoa_id uuid REFERENCES public.pessoas_cadastro(id);

-- ==================================================
-- 3. Funcoes privadas (private.*)
-- ==================================================

CREATE OR REPLACE FUNCTION private.normalizar_documento(p_valor text)
 RETURNS text
 LANGUAGE sql
 IMMUTABLE
 SET search_path TO ''
AS $function$
    select regexp_replace(coalesce(p_valor, ''), '[^0-9A-Za-z]', '', 'g');
$function$;

CREATE OR REPLACE FUNCTION private.validar_chave_assinaturas(p_chave_app text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
begin
    if p_chave_app is distinct from __ASSINATURAS_APP_KEY__ then
        raise exception 'acesso negado' using errcode='28000';
    end if;
end;
$function$;

CREATE OR REPLACE FUNCTION private.resolver_pessoa_cadastro(p_pessoa_atual uuid, p_tipo text, p_nome text, p_documento text, p_origem text)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare
    v_id uuid;
    v_doc text := private.normalizar_documento(p_documento);
    v_tipo text := case when upper(coalesce(p_tipo,'')) = 'PESSOA_JURIDICA' then 'PESSOA_JURIDICA' else 'PESSOA_FISICA' end;
    v_nome text := trim(coalesce(p_nome,''));
begin
    if v_nome = '' then
        v_nome := 'Sem nome';
    end if;

    if v_doc <> '' then
        select id into v_id
        from public.pessoas_cadastro
        where documento_normalizado = v_doc
        limit 1;
        if v_id is not null then
            update public.pessoas_cadastro
               set nome_exibicao = case when nome_exibicao = '' or nome_exibicao = 'Sem nome' then v_nome else nome_exibicao end,
                   documento = coalesce(nullif(documento,''), p_documento),
                   ativo = true,
                   atualizado_em = now()
             where id = v_id;
            return v_id;
        end if;
    end if;

    if p_pessoa_atual is not null and exists(select 1 from public.pessoas_cadastro where id=p_pessoa_atual) then
        update public.pessoas_cadastro
           set tipo_pessoa = v_tipo,
               nome_exibicao = v_nome,
               documento = case when v_doc <> '' then p_documento else documento end,
               ativo = true,
               atualizado_em = now()
         where id = p_pessoa_atual;
        return p_pessoa_atual;
    end if;

    insert into public.pessoas_cadastro(tipo_pessoa,nome_exibicao,documento,origem)
    values(v_tipo,v_nome,nullif(p_documento,''),coalesce(nullif(p_origem,''),'CADASTRO'))
    returning id into v_id;
    return v_id;
end;
$function$;

CREATE OR REPLACE FUNCTION private.upsert_pf_central(p_pessoa_id uuid, p_dados jsonb, p_endereco jsonb DEFAULT '{}'::jsonb, p_somente_vazios boolean DEFAULT false)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
begin
    if p_pessoa_id is null then return; end if;
    insert into public.pessoas_fisicas_cadastro(
        pessoa_id,sexo,nome_completo,estado_civil,regime_casamento,profissao_ocupacao,nacionalidade,
        rg,orgao_expedidor_rg,cpf,nome_pai,nome_mae,data_nascimento,uf_nascimento,cidade_nascimento,
        email,telefone,texto_adicional,tipo_endereco,logradouro,uf,cidade,bairro,cep,numero,complemento
    ) values(
        p_pessoa_id,nullif(p_dados->>'sexo',''),nullif(p_dados->>'nome_completo',''),nullif(p_dados->>'estado_civil',''),
        nullif(p_dados->>'regime_casamento',''),nullif(p_dados->>'profissao_ocupacao',''),nullif(p_dados->>'nacionalidade',''),
        nullif(p_dados->>'rg',''),nullif(p_dados->>'orgao_expedidor_rg',''),nullif(p_dados->>'cpf',''),
        nullif(p_dados->>'nome_pai',''),nullif(p_dados->>'nome_mae',''),nullif(p_dados->>'data_nascimento',''),
        nullif(p_dados->>'uf_nascimento',''),nullif(p_dados->>'cidade_nascimento',''),nullif(p_dados->>'email',''),
        nullif(p_dados->>'telefone',''),nullif(p_dados->>'texto_adicional',''),nullif(p_endereco->>'tipo_endereco',''),
        nullif(p_endereco->>'logradouro',''),nullif(p_endereco->>'uf',''),nullif(p_endereco->>'cidade',''),
        nullif(p_endereco->>'bairro',''),nullif(p_endereco->>'cep',''),nullif(p_endereco->>'numero',''),nullif(p_endereco->>'complemento','')
    )
    on conflict (pessoa_id) do update set
        sexo=case when p_somente_vazios then coalesce(public.pessoas_fisicas_cadastro.sexo,excluded.sexo) else coalesce(excluded.sexo,public.pessoas_fisicas_cadastro.sexo) end,
        nome_completo=case when p_somente_vazios then coalesce(public.pessoas_fisicas_cadastro.nome_completo,excluded.nome_completo) else coalesce(excluded.nome_completo,public.pessoas_fisicas_cadastro.nome_completo) end,
        estado_civil=case when p_somente_vazios then coalesce(public.pessoas_fisicas_cadastro.estado_civil,excluded.estado_civil) else coalesce(excluded.estado_civil,public.pessoas_fisicas_cadastro.estado_civil) end,
        regime_casamento=case when p_somente_vazios then coalesce(public.pessoas_fisicas_cadastro.regime_casamento,excluded.regime_casamento) else coalesce(excluded.regime_casamento,public.pessoas_fisicas_cadastro.regime_casamento) end,
        profissao_ocupacao=case when p_somente_vazios then coalesce(public.pessoas_fisicas_cadastro.profissao_ocupacao,excluded.profissao_ocupacao) else coalesce(excluded.profissao_ocupacao,public.pessoas_fisicas_cadastro.profissao_ocupacao) end,
        nacionalidade=case when p_somente_vazios then coalesce(public.pessoas_fisicas_cadastro.nacionalidade,excluded.nacionalidade) else coalesce(excluded.nacionalidade,public.pessoas_fisicas_cadastro.nacionalidade) end,
        rg=case when p_somente_vazios then coalesce(public.pessoas_fisicas_cadastro.rg,excluded.rg) else coalesce(excluded.rg,public.pessoas_fisicas_cadastro.rg) end,
        orgao_expedidor_rg=case when p_somente_vazios then coalesce(public.pessoas_fisicas_cadastro.orgao_expedidor_rg,excluded.orgao_expedidor_rg) else coalesce(excluded.orgao_expedidor_rg,public.pessoas_fisicas_cadastro.orgao_expedidor_rg) end,
        cpf=case when p_somente_vazios then coalesce(public.pessoas_fisicas_cadastro.cpf,excluded.cpf) else coalesce(excluded.cpf,public.pessoas_fisicas_cadastro.cpf) end,
        nome_pai=case when p_somente_vazios then coalesce(public.pessoas_fisicas_cadastro.nome_pai,excluded.nome_pai) else coalesce(excluded.nome_pai,public.pessoas_fisicas_cadastro.nome_pai) end,
        nome_mae=case when p_somente_vazios then coalesce(public.pessoas_fisicas_cadastro.nome_mae,excluded.nome_mae) else coalesce(excluded.nome_mae,public.pessoas_fisicas_cadastro.nome_mae) end,
        data_nascimento=case when p_somente_vazios then coalesce(public.pessoas_fisicas_cadastro.data_nascimento,excluded.data_nascimento) else coalesce(excluded.data_nascimento,public.pessoas_fisicas_cadastro.data_nascimento) end,
        uf_nascimento=case when p_somente_vazios then coalesce(public.pessoas_fisicas_cadastro.uf_nascimento,excluded.uf_nascimento) else coalesce(excluded.uf_nascimento,public.pessoas_fisicas_cadastro.uf_nascimento) end,
        cidade_nascimento=case when p_somente_vazios then coalesce(public.pessoas_fisicas_cadastro.cidade_nascimento,excluded.cidade_nascimento) else coalesce(excluded.cidade_nascimento,public.pessoas_fisicas_cadastro.cidade_nascimento) end,
        email=case when p_somente_vazios then coalesce(public.pessoas_fisicas_cadastro.email,excluded.email) else coalesce(excluded.email,public.pessoas_fisicas_cadastro.email) end,
        telefone=case when p_somente_vazios then coalesce(public.pessoas_fisicas_cadastro.telefone,excluded.telefone) else coalesce(excluded.telefone,public.pessoas_fisicas_cadastro.telefone) end,
        texto_adicional=case when p_somente_vazios then coalesce(public.pessoas_fisicas_cadastro.texto_adicional,excluded.texto_adicional) else coalesce(excluded.texto_adicional,public.pessoas_fisicas_cadastro.texto_adicional) end,
        tipo_endereco=case when p_somente_vazios then coalesce(public.pessoas_fisicas_cadastro.tipo_endereco,excluded.tipo_endereco) else coalesce(excluded.tipo_endereco,public.pessoas_fisicas_cadastro.tipo_endereco) end,
        logradouro=case when p_somente_vazios then coalesce(public.pessoas_fisicas_cadastro.logradouro,excluded.logradouro) else coalesce(excluded.logradouro,public.pessoas_fisicas_cadastro.logradouro) end,
        uf=case when p_somente_vazios then coalesce(public.pessoas_fisicas_cadastro.uf,excluded.uf) else coalesce(excluded.uf,public.pessoas_fisicas_cadastro.uf) end,
        cidade=case when p_somente_vazios then coalesce(public.pessoas_fisicas_cadastro.cidade,excluded.cidade) else coalesce(excluded.cidade,public.pessoas_fisicas_cadastro.cidade) end,
        bairro=case when p_somente_vazios then coalesce(public.pessoas_fisicas_cadastro.bairro,excluded.bairro) else coalesce(excluded.bairro,public.pessoas_fisicas_cadastro.bairro) end,
        cep=case when p_somente_vazios then coalesce(public.pessoas_fisicas_cadastro.cep,excluded.cep) else coalesce(excluded.cep,public.pessoas_fisicas_cadastro.cep) end,
        numero=case when p_somente_vazios then coalesce(public.pessoas_fisicas_cadastro.numero,excluded.numero) else coalesce(excluded.numero,public.pessoas_fisicas_cadastro.numero) end,
        complemento=case when p_somente_vazios then coalesce(public.pessoas_fisicas_cadastro.complemento,excluded.complemento) else coalesce(excluded.complemento,public.pessoas_fisicas_cadastro.complemento) end,
        atualizado_em=now();
end;
$function$;

CREATE OR REPLACE FUNCTION private.upsert_pj_central(p_pessoa_id uuid, p_dados jsonb, p_somente_vazios boolean DEFAULT false)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
begin
    if p_pessoa_id is null then return; end if;
    insert into public.pessoas_juridicas_cadastro(
        pessoa_id,razao_social,nome_fantasia,cnpj,email,telefone,tipo_endereco,logradouro,uf,cidade,bairro,cep,numero,complemento
    ) values(
        p_pessoa_id,nullif(p_dados->>'razao_social',''),nullif(p_dados->>'nome_fantasia',''),nullif(p_dados->>'cnpj',''),
        nullif(p_dados->>'email',''),nullif(p_dados->>'telefone',''),nullif(p_dados->>'tipo_endereco',''),nullif(p_dados->>'logradouro',''),
        nullif(p_dados->>'uf',''),nullif(p_dados->>'cidade',''),nullif(p_dados->>'bairro',''),nullif(p_dados->>'cep',''),
        nullif(p_dados->>'numero',''),nullif(p_dados->>'complemento','')
    ) on conflict(pessoa_id) do update set
        razao_social=case when p_somente_vazios then coalesce(public.pessoas_juridicas_cadastro.razao_social,excluded.razao_social) else coalesce(excluded.razao_social,public.pessoas_juridicas_cadastro.razao_social) end,
        nome_fantasia=case when p_somente_vazios then coalesce(public.pessoas_juridicas_cadastro.nome_fantasia,excluded.nome_fantasia) else coalesce(excluded.nome_fantasia,public.pessoas_juridicas_cadastro.nome_fantasia) end,
        cnpj=case when p_somente_vazios then coalesce(public.pessoas_juridicas_cadastro.cnpj,excluded.cnpj) else coalesce(excluded.cnpj,public.pessoas_juridicas_cadastro.cnpj) end,
        email=case when p_somente_vazios then coalesce(public.pessoas_juridicas_cadastro.email,excluded.email) else coalesce(excluded.email,public.pessoas_juridicas_cadastro.email) end,
        telefone=case when p_somente_vazios then coalesce(public.pessoas_juridicas_cadastro.telefone,excluded.telefone) else coalesce(excluded.telefone,public.pessoas_juridicas_cadastro.telefone) end,
        tipo_endereco=case when p_somente_vazios then coalesce(public.pessoas_juridicas_cadastro.tipo_endereco,excluded.tipo_endereco) else coalesce(excluded.tipo_endereco,public.pessoas_juridicas_cadastro.tipo_endereco) end,
        logradouro=case when p_somente_vazios then coalesce(public.pessoas_juridicas_cadastro.logradouro,excluded.logradouro) else coalesce(excluded.logradouro,public.pessoas_juridicas_cadastro.logradouro) end,
        uf=case when p_somente_vazios then coalesce(public.pessoas_juridicas_cadastro.uf,excluded.uf) else coalesce(excluded.uf,public.pessoas_juridicas_cadastro.uf) end,
        cidade=case when p_somente_vazios then coalesce(public.pessoas_juridicas_cadastro.cidade,excluded.cidade) else coalesce(excluded.cidade,public.pessoas_juridicas_cadastro.cidade) end,
        bairro=case when p_somente_vazios then coalesce(public.pessoas_juridicas_cadastro.bairro,excluded.bairro) else coalesce(excluded.bairro,public.pessoas_juridicas_cadastro.bairro) end,
        cep=case when p_somente_vazios then coalesce(public.pessoas_juridicas_cadastro.cep,excluded.cep) else coalesce(excluded.cep,public.pessoas_juridicas_cadastro.cep) end,
        numero=case when p_somente_vazios then coalesce(public.pessoas_juridicas_cadastro.numero,excluded.numero) else coalesce(excluded.numero,public.pessoas_juridicas_cadastro.numero) end,
        complemento=case when p_somente_vazios then coalesce(public.pessoas_juridicas_cadastro.complemento,excluded.complemento) else coalesce(excluded.complemento,public.pessoas_juridicas_cadastro.complemento) end,
        atualizado_em=now();
end;
$function$;

CREATE OR REPLACE FUNCTION private.atualizar_compatibilidade_cliente(p_cliente_id integer)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare
    v_tem boolean;
    v_tipo text;
begin
    select exists(
        select 1
        from public.representacao_representados rd
        join public.representacoes r on r.id=rd.representacao_id
        where rd.cliente_id=p_cliente_id
          and r.ativo
          and (r.validade_inicio is null or r.validade_inicio <= current_date)
          and (r.validade_fim is null or r.validade_fim >= current_date)
    ) into v_tem;
    select tipo_cliente into v_tipo from public.clientes where id=p_cliente_id;
    update public.clientes
       set tem_procurador = case when v_tem then 1 else 0 end,
           quem_assina = case when v_tem or v_tipo='PESSOA_JURIDICA' then 'PROCURADOR' else 'PROPRIETARIO' end,
           atualizado_em = now()::text
     where id=p_cliente_id;
end;
$function$;

CREATE OR REPLACE FUNCTION private.sincronizar_representacoes_legadas(p_cliente_id integer)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare
    pr record;
    v_rep uuid;
begin
    delete from public.representacoes r
     where r.origem='SINCRONIZACAO_LEGADO'
       and exists(select 1 from public.representacao_representados rd where rd.representacao_id=r.id and rd.cliente_id=p_cliente_id);

    for pr in
        select * from public.procuradores where cliente_id=p_cliente_id and pessoa_id is not null order by principal desc,id
    loop
        if exists(
            select 1
            from public.representacoes r
            join public.representacao_representantes rr on rr.representacao_id=r.id
            join public.representacao_representados rd on rd.representacao_id=r.id
            where r.ativo and r.origem <> 'SINCRONIZACAO_LEGADO'
              and rr.pessoa_id=pr.pessoa_id and rd.cliente_id=p_cliente_id
        ) then
            continue;
        end if;
        if exists(
            select 1
            from public.representacoes r
            join public.representacao_representantes rr on rr.representacao_id=r.id
            join public.representacao_representados rd on rd.representacao_id=r.id
            where r.ativo and r.origem='SINCRONIZACAO_LEGADO'
              and rr.pessoa_id=pr.pessoa_id and rd.cliente_id=p_cliente_id
        ) then
            continue;
        end if;

        insert into public.representacoes(natureza,modo_atuacao,principal,ativo,origem)
        values('LEGADO','INDIVIDUAL',pr.principal=1,true,'SINCRONIZACAO_LEGADO')
        returning id into v_rep;
        insert into public.representacao_representantes(representacao_id,pessoa_id,papel,principal,procurador_legado_id)
        values(v_rep,pr.pessoa_id,coalesce(nullif(pr.tipo_representacao,''),'PROCURADOR'),pr.principal=1,pr.id);
        insert into public.representacao_representados(representacao_id,cliente_id)
        values(v_rep,p_cliente_id);
    end loop;

    perform private.atualizar_compatibilidade_cliente(p_cliente_id);
end;
$function$;

CREATE OR REPLACE FUNCTION private.sync_cliente_pessoa_before_write()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
begin
    new.pessoa_id := private.resolver_pessoa_cadastro(
        new.pessoa_id,
        coalesce(new.tipo_cliente,'PESSOA_FISICA'),
        coalesce(nullif(new.nome_exibicao,''),nullif(new.nome,''),'Sem nome'),
        new.cpf_cnpj,
        'CLIENTE_LEGADO'
    );
    return new;
end;
$function$;

CREATE OR REPLACE FUNCTION private.sync_pf_pessoa_before_write()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare v_cliente_pessoa uuid;
begin
    select pessoa_id into v_cliente_pessoa from public.clientes where id=new.cliente_id;
    new.pessoa_id := private.resolver_pessoa_cadastro(
        coalesce(new.pessoa_id,v_cliente_pessoa),'PESSOA_FISICA',new.nome_completo,new.cpf,'PESSOA_FISICA_LEGADO'
    );
    if v_cliente_pessoa is distinct from new.pessoa_id then
        update public.clientes set pessoa_id=new.pessoa_id where id=new.cliente_id;
    end if;
    return new;
end;
$function$;

CREATE OR REPLACE FUNCTION private.sync_pf_qualificacao_after_write()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare v_end jsonb;
begin
    select coalesce(to_jsonb(ep),'{}'::jsonb) into v_end from public.enderecos_proprietario ep where ep.pessoa_fisica_id=new.id;
    perform private.upsert_pf_central(new.pessoa_id,to_jsonb(new),coalesce(v_end,'{}'::jsonb),false);
    return new;
end; $function$;

CREATE OR REPLACE FUNCTION private.sync_pj_pessoa_before_write()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare v_cliente_pessoa uuid;
begin
    select pessoa_id into v_cliente_pessoa from public.clientes where id=new.cliente_id;
    new.pessoa_id := private.resolver_pessoa_cadastro(
        coalesce(new.pessoa_id,v_cliente_pessoa),'PESSOA_JURIDICA',new.razao_social,new.cnpj,'PESSOA_JURIDICA_LEGADO'
    );
    if v_cliente_pessoa is distinct from new.pessoa_id then
        update public.clientes set pessoa_id=new.pessoa_id where id=new.cliente_id;
    end if;
    return new;
end;
$function$;

CREATE OR REPLACE FUNCTION private.sync_pj_qualificacao_after_write()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
begin perform private.upsert_pj_central(new.pessoa_id,to_jsonb(new),false); return new; end; $function$;

CREATE OR REPLACE FUNCTION private.sync_conjuge_pessoa_before_write()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
begin
    new.pessoa_id := private.resolver_pessoa_cadastro(
        new.pessoa_id,'PESSOA_FISICA',new.nome_completo,new.cpf,'CONJUGE_LEGADO'
    );
    return new;
end;
$function$;

CREATE OR REPLACE FUNCTION private.sync_conjuge_qualificacao_after_write()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
begin perform private.upsert_pf_central(new.pessoa_id,to_jsonb(new),'{}'::jsonb,false); return new; end; $function$;

CREATE OR REPLACE FUNCTION private.sync_procurador_pessoa_before_write()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
begin
    new.pessoa_id := private.resolver_pessoa_cadastro(
        new.pessoa_id,'PESSOA_FISICA',new.nome_completo,new.cpf,'REPRESENTANTE_LEGADO'
    );
    return new;
end;
$function$;

CREATE OR REPLACE FUNCTION private.sync_procurador_qualificacao_after_write()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
begin perform private.upsert_pf_central(new.pessoa_id,to_jsonb(new),to_jsonb(new),false); return new; end; $function$;

CREATE OR REPLACE FUNCTION private.procuradores_after_change_sync_representacoes()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
begin
    if tg_op='DELETE' then
        perform private.sincronizar_representacoes_legadas(old.cliente_id);
        return old;
    end if;
    perform private.sincronizar_representacoes_legadas(new.cliente_id);
    if tg_op='UPDATE' and old.cliente_id is distinct from new.cliente_id then
        perform private.sincronizar_representacoes_legadas(old.cliente_id);
    end if;
    return new;
end;
$function$;

-- ==================================================
-- 4. Triggers
-- ==================================================

DROP TRIGGER IF EXISTS trg_clientes_sync_pessoa ON public.clientes;
CREATE TRIGGER trg_clientes_sync_pessoa
    BEFORE INSERT OR UPDATE ON public.clientes
    FOR EACH ROW EXECUTE FUNCTION private.sync_cliente_pessoa_before_write();

DROP TRIGGER IF EXISTS trg_pf_sync_pessoa ON public.pessoas_fisicas;
CREATE TRIGGER trg_pf_sync_pessoa
    BEFORE INSERT OR UPDATE ON public.pessoas_fisicas
    FOR EACH ROW EXECUTE FUNCTION private.sync_pf_pessoa_before_write();

DROP TRIGGER IF EXISTS trg_pf_sync_qualificacao ON public.pessoas_fisicas;
CREATE TRIGGER trg_pf_sync_qualificacao
    AFTER INSERT OR UPDATE ON public.pessoas_fisicas
    FOR EACH ROW EXECUTE FUNCTION private.sync_pf_qualificacao_after_write();

DROP TRIGGER IF EXISTS trg_pj_sync_pessoa ON public.pessoas_juridicas;
CREATE TRIGGER trg_pj_sync_pessoa
    BEFORE INSERT OR UPDATE ON public.pessoas_juridicas
    FOR EACH ROW EXECUTE FUNCTION private.sync_pj_pessoa_before_write();

DROP TRIGGER IF EXISTS trg_pj_sync_qualificacao ON public.pessoas_juridicas;
CREATE TRIGGER trg_pj_sync_qualificacao
    AFTER INSERT OR UPDATE ON public.pessoas_juridicas
    FOR EACH ROW EXECUTE FUNCTION private.sync_pj_qualificacao_after_write();

DROP TRIGGER IF EXISTS trg_conjuge_sync_pessoa ON public.conjuges;
CREATE TRIGGER trg_conjuge_sync_pessoa
    BEFORE INSERT OR UPDATE ON public.conjuges
    FOR EACH ROW EXECUTE FUNCTION private.sync_conjuge_pessoa_before_write();

DROP TRIGGER IF EXISTS trg_conjuge_sync_qualificacao ON public.conjuges;
CREATE TRIGGER trg_conjuge_sync_qualificacao
    AFTER INSERT OR UPDATE ON public.conjuges
    FOR EACH ROW EXECUTE FUNCTION private.sync_conjuge_qualificacao_after_write();

DROP TRIGGER IF EXISTS trg_procurador_sync_pessoa ON public.procuradores;
CREATE TRIGGER trg_procurador_sync_pessoa
    BEFORE INSERT OR UPDATE ON public.procuradores
    FOR EACH ROW EXECUTE FUNCTION private.sync_procurador_pessoa_before_write();

DROP TRIGGER IF EXISTS trg_procurador_sync_qualificacao ON public.procuradores;
CREATE TRIGGER trg_procurador_sync_qualificacao
    AFTER INSERT OR UPDATE ON public.procuradores
    FOR EACH ROW EXECUTE FUNCTION private.sync_procurador_qualificacao_after_write();

DROP TRIGGER IF EXISTS trg_procuradores_sync_representacoes ON public.procuradores;
CREATE TRIGGER trg_procuradores_sync_representacoes
    AFTER INSERT OR UPDATE OR DELETE ON public.procuradores
    FOR EACH ROW EXECUTE FUNCTION private.procuradores_after_change_sync_representacoes();

-- ==================================================
-- 5. RPCs publicas (schema_version = 1)
-- ==================================================

CREATE OR REPLACE FUNCTION public.listar_pessoas_assinatura_v1(p_chave_app text DEFAULT NULL::text)
 RETURNS SETOF jsonb
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
begin
    perform private.validar_chave_assinaturas(p_chave_app);
    return query
    select jsonb_build_object(
        'schema_version',1,
        'pessoa_id',pc.id::text,
        'tipo_pessoa',pc.tipo_pessoa,
        'nome_display',pc.nome_exibicao,
        'documento',pc.documento,
        'documento_normalizado',pc.documento_normalizado,
        'search',concat_ws(' ',pc.nome_busca,pc.documento_normalizado,
            coalesce((select string_agg(concat_ws(' ',c.nome,c.nome_exibicao,c.cpf_cnpj,pf.nome_completo,pf.cpf,pj.razao_social,pj.nome_fantasia,pj.cnpj),' ')
                      from public.clientes c
                      left join public.pessoas_fisicas pf on pf.cliente_id=c.id
                      left join public.pessoas_juridicas pj on pj.cliente_id=c.id
                      where c.pessoa_id=pc.id),''),
            coalesce((select string_agg(concat_ws(' ',cg.nome_completo,cg.cpf),' ') from public.conjuges cg where cg.pessoa_id=pc.id),''),
            coalesce((select string_agg(concat_ws(' ',pr.nome_completo,pr.cpf,pr.tipo_representacao),' ') from public.procuradores pr where pr.pessoa_id=pc.id),'')
        ),
        'vinculos',jsonb_build_object(
            'clientes',coalesce((select jsonb_agg(jsonb_build_object(
                'cliente_id',c.id::text,
                'nome',coalesce(nullif(c.nome_documental,''),nullif(c.nome_exibicao,''),c.nome),
                'tipo_cliente',c.tipo_cliente,
                'condicao_juridica',c.condicao_juridica
            ) order by c.id) from public.clientes c where c.pessoa_id=pc.id),'[]'::jsonb),
            'conjuges',coalesce((select jsonb_agg(jsonb_build_object(
                'conjuge_id',cg.id::text,
                'nome',cg.nome_completo,
                'pessoa_fisica_id',cg.pessoa_fisica_id::text
            ) order by cg.id) from public.conjuges cg where cg.pessoa_id=pc.id),'[]'::jsonb),
            'representantes_legados',coalesce((select jsonb_agg(jsonb_build_object(
                'procurador_id',pr.id::text,
                'cliente_id',pr.cliente_id::text,
                'tipo_representacao',pr.tipo_representacao,
                'principal',pr.principal
            ) order by pr.id) from public.procuradores pr where pr.pessoa_id=pc.id),'[]'::jsonb)
        ),
        'papeis_representacao',coalesce((
            select jsonb_agg(distinct rr.papel)
            from public.representacao_representantes rr
            join public.representacoes r on r.id=rr.representacao_id
            where rr.pessoa_id=pc.id and r.ativo
        ),'[]'::jsonb)
    )
    from public.pessoas_cadastro pc
    where pc.ativo
    order by pc.nome_busca,pc.id;
end;
$function$;

CREATE OR REPLACE FUNCTION public.obter_pessoa_assinatura_v1(p_pessoa_id uuid, p_chave_app text DEFAULT NULL::text)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare v_result jsonb;
begin
    perform private.validar_chave_assinaturas(p_chave_app);
    select jsonb_build_object(
        'schema_version',1,'pessoa_id',pc.id::text,'tipo_pessoa',pc.tipo_pessoa,'nome_display',pc.nome_exibicao,
        'documento',pc.documento,'ativo',pc.ativo,
        'pessoa_fisica',coalesce(to_jsonb(pfc),'{}'::jsonb),
        'pessoa_juridica',coalesce(to_jsonb(pjc),'{}'::jsonb),
        'clientes',coalesce((select jsonb_agg(jsonb_build_object('cliente_id',c.id::text,'nome',coalesce(nullif(c.nome_documental,''),c.nome_exibicao,c.nome),'condicao_juridica',c.condicao_juridica) order by c.id) from public.clientes c where c.pessoa_id=pc.id),'[]'::jsonb),
        'representa',coalesce((select jsonb_agg(jsonb_build_object('representacao_id',r.id::text,'papel',rr.papel,'ativo',r.ativo,'modo_atuacao',r.modo_atuacao) order by r.criado_em,r.id) from public.representacao_representantes rr join public.representacoes r on r.id=rr.representacao_id where rr.pessoa_id=pc.id),'[]'::jsonb)
    ) into v_result
    from public.pessoas_cadastro pc
    left join public.pessoas_fisicas_cadastro pfc on pfc.pessoa_id=pc.id
    left join public.pessoas_juridicas_cadastro pjc on pjc.pessoa_id=pc.id
    where pc.id=p_pessoa_id;
    if v_result is null then raise exception 'pessoa nao encontrada'; end if;
    return v_result;
end;
$function$;

CREATE OR REPLACE FUNCTION public.salvar_pessoa_assinatura_v1(p_dados jsonb, p_chave_app text DEFAULT NULL::text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare
    v_id uuid;
    v_tipo text := upper(coalesce(nullif(p_dados->>'tipo_pessoa',''),'PESSOA_FISICA'));
    v_nome text;
    v_doc text;
    v_pf jsonb := coalesce(p_dados->'pessoa_fisica','{}'::jsonb);
    v_pj jsonb := coalesce(p_dados->'pessoa_juridica','{}'::jsonb);
    v_end jsonb := coalesce(p_dados->'endereco','{}'::jsonb);
begin
    perform private.validar_chave_assinaturas(p_chave_app);
    if v_tipo not in ('PESSOA_FISICA','PESSOA_JURIDICA') then raise exception 'tipo_pessoa invalido'; end if;
    v_nome := coalesce(nullif(p_dados->>'nome_exibicao',''),nullif(v_pf->>'nome_completo',''),nullif(v_pj->>'razao_social',''));
    v_doc := coalesce(nullif(p_dados->>'documento',''),nullif(v_pf->>'cpf',''),nullif(v_pj->>'cnpj',''));
    if v_nome is null then raise exception 'nome obrigatorio'; end if;

    if nullif(p_dados->>'pessoa_id','') is not null then
        begin v_id := (p_dados->>'pessoa_id')::uuid; exception when others then raise exception 'pessoa_id invalido'; end;
    end if;
    v_id := private.resolver_pessoa_cadastro(v_id,v_tipo,v_nome,v_doc,'RPC_V1');

    update public.pessoas_cadastro set tipo_pessoa=v_tipo,nome_exibicao=v_nome,documento=coalesce(v_doc,documento),ativo=true where id=v_id;
    if v_tipo='PESSOA_JURIDICA' then
        perform private.upsert_pj_central(v_id,v_pj || jsonb_build_object('razao_social',coalesce(nullif(v_pj->>'razao_social',''),v_nome),'cnpj',coalesce(nullif(v_pj->>'cnpj',''),v_doc)),false);
    else
        perform private.upsert_pf_central(v_id,v_pf || jsonb_build_object('nome_completo',coalesce(nullif(v_pf->>'nome_completo',''),v_nome),'cpf',coalesce(nullif(v_pf->>'cpf',''),v_doc)),v_end,false);
    end if;

    -- Mantém qualificações legadas já ligadas à mesma pessoa coerentes, sem criar novos contextos automaticamente.
    if v_tipo='PESSOA_FISICA' then
        update public.pessoas_fisicas pf set
            nome_completo=coalesce(nullif(v_pf->>'nome_completo',''),pf.nome_completo),cpf=coalesce(nullif(v_pf->>'cpf',''),pf.cpf),
            rg=coalesce(nullif(v_pf->>'rg',''),pf.rg),orgao_expedidor_rg=coalesce(nullif(v_pf->>'orgao_expedidor_rg',''),pf.orgao_expedidor_rg),
            nacionalidade=coalesce(nullif(v_pf->>'nacionalidade',''),pf.nacionalidade),sexo=coalesce(nullif(v_pf->>'sexo',''),pf.sexo),
            estado_civil=coalesce(nullif(v_pf->>'estado_civil',''),pf.estado_civil),regime_casamento=coalesce(nullif(v_pf->>'regime_casamento',''),pf.regime_casamento),
            profissao_ocupacao=coalesce(nullif(v_pf->>'profissao_ocupacao',''),pf.profissao_ocupacao),data_nascimento=coalesce(nullif(v_pf->>'data_nascimento',''),pf.data_nascimento),
            uf_nascimento=coalesce(nullif(v_pf->>'uf_nascimento',''),pf.uf_nascimento),cidade_nascimento=coalesce(nullif(v_pf->>'cidade_nascimento',''),pf.cidade_nascimento),
            nome_pai=coalesce(nullif(v_pf->>'nome_pai',''),pf.nome_pai),nome_mae=coalesce(nullif(v_pf->>'nome_mae',''),pf.nome_mae),
            email=coalesce(nullif(v_pf->>'email',''),pf.email),telefone=coalesce(nullif(v_pf->>'telefone',''),pf.telefone),atualizado_em=now()::text
        where pf.pessoa_id=v_id;

        update public.procuradores pr set
            nome_completo=coalesce(nullif(v_pf->>'nome_completo',''),pr.nome_completo),cpf=coalesce(nullif(v_pf->>'cpf',''),pr.cpf),
            rg=coalesce(nullif(v_pf->>'rg',''),pr.rg),orgao_expedidor_rg=coalesce(nullif(v_pf->>'orgao_expedidor_rg',''),pr.orgao_expedidor_rg),
            nacionalidade=coalesce(nullif(v_pf->>'nacionalidade',''),pr.nacionalidade),sexo=coalesce(nullif(v_pf->>'sexo',''),pr.sexo),
            estado_civil=coalesce(nullif(v_pf->>'estado_civil',''),pr.estado_civil),regime_casamento=coalesce(nullif(v_pf->>'regime_casamento',''),pr.regime_casamento),
            profissao_ocupacao=coalesce(nullif(v_pf->>'profissao_ocupacao',''),pr.profissao_ocupacao),data_nascimento=coalesce(nullif(v_pf->>'data_nascimento',''),pr.data_nascimento),
            uf_nascimento=coalesce(nullif(v_pf->>'uf_nascimento',''),pr.uf_nascimento),cidade_nascimento=coalesce(nullif(v_pf->>'cidade_nascimento',''),pr.cidade_nascimento),
            nome_pai=coalesce(nullif(v_pf->>'nome_pai',''),pr.nome_pai),nome_mae=coalesce(nullif(v_pf->>'nome_mae',''),pr.nome_mae),
            email=coalesce(nullif(v_pf->>'email',''),pr.email),telefone=coalesce(nullif(v_pf->>'telefone',''),pr.telefone),
            texto_adicional=coalesce(nullif(v_pf->>'texto_adicional',''),pr.texto_adicional),
            tipo_endereco=coalesce(nullif(v_end->>'tipo_endereco',''),pr.tipo_endereco),logradouro=coalesce(nullif(v_end->>'logradouro',''),pr.logradouro),
            uf=coalesce(nullif(v_end->>'uf',''),pr.uf),cidade=coalesce(nullif(v_end->>'cidade',''),pr.cidade),bairro=coalesce(nullif(v_end->>'bairro',''),pr.bairro),
            cep=coalesce(nullif(v_end->>'cep',''),pr.cep),numero=coalesce(nullif(v_end->>'numero',''),pr.numero),complemento=coalesce(nullif(v_end->>'complemento',''),pr.complemento),
            atualizado_em=now()::text
        where pr.pessoa_id=v_id;
    else
        update public.pessoas_juridicas pj set
            razao_social=coalesce(nullif(v_pj->>'razao_social',''),pj.razao_social),nome_fantasia=coalesce(nullif(v_pj->>'nome_fantasia',''),pj.nome_fantasia),
            cnpj=coalesce(nullif(v_pj->>'cnpj',''),pj.cnpj),email=coalesce(nullif(v_pj->>'email',''),pj.email),telefone=coalesce(nullif(v_pj->>'telefone',''),pj.telefone),
            tipo_endereco=coalesce(nullif(v_pj->>'tipo_endereco',''),pj.tipo_endereco),logradouro=coalesce(nullif(v_pj->>'logradouro',''),pj.logradouro),
            uf=coalesce(nullif(v_pj->>'uf',''),pj.uf),cidade=coalesce(nullif(v_pj->>'cidade',''),pj.cidade),bairro=coalesce(nullif(v_pj->>'bairro',''),pj.bairro),
            cep=coalesce(nullif(v_pj->>'cep',''),pj.cep),numero=coalesce(nullif(v_pj->>'numero',''),pj.numero),complemento=coalesce(nullif(v_pj->>'complemento',''),pj.complemento),
            atualizado_em=now()::text
        where pj.pessoa_id=v_id;
    end if;

    return jsonb_build_object('schema_version',1,'pessoa_id',v_id::text,'tipo_pessoa',v_tipo);
end;
$function$;

CREATE OR REPLACE FUNCTION public.obter_contexto_assinatura_v1(p_cliente_id text, p_chave_app text DEFAULT NULL::text)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare
    v_id integer;
    v_conjuge_pessoa uuid;
    v_result jsonb;
begin
    perform private.validar_chave_assinaturas(p_chave_app);
    begin v_id:=p_cliente_id::integer; exception when others then raise exception 'cliente invalido'; end;
    if not exists(select 1 from public.clientes where id=v_id) then raise exception 'cliente nao encontrado'; end if;
    select cg.pessoa_id into v_conjuge_pessoa from public.pessoas_fisicas pf join public.conjuges cg on cg.pessoa_fisica_id=pf.id where pf.cliente_id=v_id limit 1;

    select jsonb_build_object(
        'schema_version',1,'cliente_id',c.id::text,
        'titular',jsonb_build_object(
            'pessoa_id',pc.id::text,'tipo_pessoa',pc.tipo_pessoa,
            'nome',coalesce(nullif(c.nome_documental,''),nullif(c.nome_exibicao,''),nullif(pc.nome_exibicao,''),c.nome),
            'nome_cadastro',pc.nome_exibicao,'documento',pc.documento,'condicao_juridica',c.condicao_juridica,
            'qualificacao_central',case when pc.tipo_pessoa='PESSOA_JURIDICA' then coalesce(to_jsonb(pjc),'{}'::jsonb) else coalesce(to_jsonb(pfc),'{}'::jsonb) end,
            'pessoa_fisica',coalesce(to_jsonb(pf),'{}'::jsonb),'pessoa_juridica',coalesce(to_jsonb(pj),'{}'::jsonb),'endereco',coalesce(to_jsonb(ep),'{}'::jsonb)
        ),
        'conjuge',case when cg.id is null then '{}'::jsonb else jsonb_build_object(
            'conjuge_id',cg.id::text,'pessoa_id',cg.pessoa_id::text,'nome',cg.nome_completo,'cpf',cg.cpf,
            'qualificacao_central',coalesce(to_jsonb(cgc),'{}'::jsonb),'dados',to_jsonb(cg)
        ) end,
        'representacoes',coalesce((
            select jsonb_agg(jsonb_build_object(
                'representacao_id',r.id::text,'natureza',r.natureza,'modo_atuacao',r.modo_atuacao,'principal',r.principal,
                'ativo',r.ativo,'vigente',(r.ativo and (r.validade_inicio is null or r.validade_inicio<=current_date) and (r.validade_fim is null or r.validade_fim>=current_date)),
                'documento_base',r.documento_base,'referencia_documento',r.referencia_documento,'escopo_poderes',r.escopo_poderes,
                'validade_inicio',r.validade_inicio,'validade_fim',r.validade_fim,'observacoes',r.observacoes,'origem',r.origem,
                'representantes',coalesce((select jsonb_agg(jsonb_build_object(
                    'pessoa_id',pcr.id::text,'nome',pcr.nome_exibicao,'cpf_cnpj',pcr.documento,'papel',rr.papel,'principal',rr.principal,'ordem',rr.ordem,
                    'procurador_legado_id',rr.procurador_legado_id,
                    'qualificacao_central',case when pcr.tipo_pessoa='PESSOA_JURIDICA' then coalesce(to_jsonb(pjcr),'{}'::jsonb) else coalesce(to_jsonb(pfcr),'{}'::jsonb) end
                ) order by rr.ordem,rr.id)
                from public.representacao_representantes rr
                join public.pessoas_cadastro pcr on pcr.id=rr.pessoa_id
                left join public.pessoas_fisicas_cadastro pfcr on pfcr.pessoa_id=pcr.id
                left join public.pessoas_juridicas_cadastro pjcr on pjcr.pessoa_id=pcr.id
                where rr.representacao_id=r.id),'[]'::jsonb),
                'representados',coalesce((select jsonb_agg(case when rd.cliente_id is not null then jsonb_build_object(
                    'tipo','CLIENTE','cliente_id',cr.id::text,'pessoa_id',cr.pessoa_id::text,'nome',coalesce(nullif(cr.nome_documental,''),nullif(cr.nome_exibicao,''),pca.nome_exibicao,cr.nome)
                ) else jsonb_build_object('tipo','PESSOA','pessoa_id',pca2.id::text,'nome',pca2.nome_exibicao,'documento',pca2.documento) end order by rd.criado_em,rd.id)
                from public.representacao_representados rd
                left join public.clientes cr on cr.id=rd.cliente_id
                left join public.pessoas_cadastro pca on pca.id=cr.pessoa_id
                left join public.pessoas_cadastro pca2 on pca2.id=rd.pessoa_id
                where rd.representacao_id=r.id),'[]'::jsonb)
            ) order by r.principal desc,r.ativo desc,r.criado_em,r.id)
            from public.representacoes r where exists(select 1 from public.representacao_representados rd where rd.representacao_id=r.id and (rd.cliente_id=v_id or (v_conjuge_pessoa is not null and rd.pessoa_id=v_conjuge_pessoa)))
        ),'[]'::jsonb),
        'compatibilidade_legado',jsonb_build_object('quem_assina',c.quem_assina,'tem_procurador',c.tem_procurador,
            'procuradores',coalesce((select jsonb_agg(to_jsonb(pr) order by pr.principal desc,pr.id) from public.procuradores pr where pr.cliente_id=c.id),'[]'::jsonb))
    ) into v_result
    from public.clientes c
    left join public.pessoas_cadastro pc on pc.id=c.pessoa_id
    left join public.pessoas_fisicas_cadastro pfc on pfc.pessoa_id=pc.id
    left join public.pessoas_juridicas_cadastro pjc on pjc.pessoa_id=pc.id
    left join public.pessoas_fisicas pf on pf.cliente_id=c.id
    left join public.pessoas_juridicas pj on pj.cliente_id=c.id
    left join public.enderecos_proprietario ep on ep.pessoa_fisica_id=pf.id
    left join public.conjuges cg on cg.pessoa_fisica_id=pf.id
    left join public.pessoas_fisicas_cadastro cgc on cgc.pessoa_id=cg.pessoa_id
    where c.id=v_id;
    return v_result;
end;
$function$;

CREATE OR REPLACE FUNCTION public.salvar_representacao_assinatura_v1(p_dados jsonb, p_chave_app text DEFAULT NULL::text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare
    v_id uuid;
    v_item jsonb;
    v_pessoa uuid;
    v_cliente integer;
    v_old_clientes integer[] := '{}'::integer[];
    v_new_clientes integer[] := '{}'::integer[];
    v_modo text;
begin
    perform private.validar_chave_assinaturas(p_chave_app);
    v_modo := upper(coalesce(nullif(p_dados->>'modo_atuacao',''),'INDIVIDUAL'));
    if v_modo not in ('INDIVIDUAL','CONJUNTA','QUALQUER_UM') then
        raise exception 'modo_atuacao invalido';
    end if;

    if coalesce(p_dados->>'representacao_id','') <> '' then
        begin v_id := (p_dados->>'representacao_id')::uuid;
        exception when others then raise exception 'representacao_id invalido'; end;
        if not exists(select 1 from public.representacoes where id=v_id) then
            raise exception 'representacao nao encontrada';
        end if;
        select coalesce(array_agg(distinct cliente_id) filter(where cliente_id is not null),'{}'::integer[])
          into v_old_clientes
          from public.representacao_representados where representacao_id=v_id;
        update public.representacoes set
            natureza=coalesce(nullif(p_dados->>'natureza',''),natureza),
            modo_atuacao=v_modo,
            principal=coalesce((p_dados->>'principal')::boolean,principal),
            ativo=coalesce((p_dados->>'ativo')::boolean,ativo),
            documento_base=case when p_dados ? 'documento_base' then nullif(p_dados->>'documento_base','') else documento_base end,
            referencia_documento=case when p_dados ? 'referencia_documento' then nullif(p_dados->>'referencia_documento','') else referencia_documento end,
            escopo_poderes=case when p_dados ? 'escopo_poderes' then nullif(p_dados->>'escopo_poderes','') else escopo_poderes end,
            validade_inicio=case when p_dados ? 'validade_inicio' and nullif(p_dados->>'validade_inicio','') is not null then (p_dados->>'validade_inicio')::date when p_dados ? 'validade_inicio' then null else validade_inicio end,
            validade_fim=case when p_dados ? 'validade_fim' and nullif(p_dados->>'validade_fim','') is not null then (p_dados->>'validade_fim')::date when p_dados ? 'validade_fim' then null else validade_fim end,
            observacoes=case when p_dados ? 'observacoes' then nullif(p_dados->>'observacoes','') else observacoes end,
            origem=case when origem='SINCRONIZACAO_LEGADO' then 'MANUAL' else origem end,
            atualizado_em=now()
        where id=v_id;
        delete from public.representacao_representantes where representacao_id=v_id;
        delete from public.representacao_representados where representacao_id=v_id;
    else
        insert into public.representacoes(
            natureza,modo_atuacao,principal,ativo,documento_base,referencia_documento,escopo_poderes,
            validade_inicio,validade_fim,observacoes,origem
        ) values(
            coalesce(nullif(p_dados->>'natureza',''),'REPRESENTACAO'),v_modo,
            coalesce((p_dados->>'principal')::boolean,false),coalesce((p_dados->>'ativo')::boolean,true),
            nullif(p_dados->>'documento_base',''),nullif(p_dados->>'referencia_documento',''),nullif(p_dados->>'escopo_poderes',''),
            case when nullif(p_dados->>'validade_inicio','') is not null then (p_dados->>'validade_inicio')::date end,
            case when nullif(p_dados->>'validade_fim','') is not null then (p_dados->>'validade_fim')::date end,
            nullif(p_dados->>'observacoes',''),'MANUAL'
        ) returning id into v_id;
    end if;

    if jsonb_array_length(coalesce(p_dados->'representantes','[]'::jsonb))=0 then
        raise exception 'informe ao menos um representante';
    end if;
    for v_item in select value from jsonb_array_elements(coalesce(p_dados->'representantes','[]'::jsonb)) loop
        begin v_pessoa := (v_item->>'pessoa_id')::uuid;
        exception when others then raise exception 'pessoa_id de representante invalido'; end;
        if not exists(select 1 from public.pessoas_cadastro where id=v_pessoa and ativo) then
            raise exception 'representante nao encontrado';
        end if;
        insert into public.representacao_representantes(
            representacao_id,pessoa_id,papel,principal,ordem,procurador_legado_id
        ) values(
            v_id,v_pessoa,coalesce(nullif(v_item->>'papel',''),'PROCURADOR'),
            coalesce((v_item->>'principal')::boolean,false),coalesce((v_item->>'ordem')::integer,0),
            case when nullif(v_item->>'procurador_legado_id','') is not null then (v_item->>'procurador_legado_id')::integer end
        );
    end loop;

    if jsonb_array_length(coalesce(p_dados->'representados','[]'::jsonb))=0 then
        raise exception 'informe ao menos um representado';
    end if;
    for v_item in select value from jsonb_array_elements(coalesce(p_dados->'representados','[]'::jsonb)) loop
        if nullif(v_item->>'cliente_id','') is not null then
            begin v_cliente := (v_item->>'cliente_id')::integer;
            exception when others then raise exception 'cliente_id representado invalido'; end;
            if not exists(select 1 from public.clientes where id=v_cliente) then
                raise exception 'cliente representado nao encontrado';
            end if;
            insert into public.representacao_representados(representacao_id,cliente_id) values(v_id,v_cliente);
            v_new_clientes := array_append(v_new_clientes,v_cliente);
        elsif nullif(v_item->>'pessoa_id','') is not null then
            begin v_pessoa := (v_item->>'pessoa_id')::uuid;
            exception when others then raise exception 'pessoa_id representada invalido'; end;
            if not exists(select 1 from public.pessoas_cadastro where id=v_pessoa and ativo) then
                raise exception 'pessoa representada nao encontrada';
            end if;
            insert into public.representacao_representados(representacao_id,pessoa_id) values(v_id,v_pessoa);
        else
            raise exception 'cada representado deve informar cliente_id ou pessoa_id';
        end if;
    end loop;

    for v_cliente in select distinct x from unnest(v_old_clientes || v_new_clientes) x loop
        perform private.atualizar_compatibilidade_cliente(v_cliente);
    end loop;

    return jsonb_build_object('schema_version',1,'representacao_id',v_id::text);
end;
$function$;

CREATE OR REPLACE FUNCTION public.desativar_representacao_assinatura_v1(p_representacao_id uuid, p_chave_app text DEFAULT NULL::text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare
    v_cliente integer;
begin
    perform private.validar_chave_assinaturas(p_chave_app);
    if not exists(select 1 from public.representacoes where id=p_representacao_id) then
        raise exception 'representacao nao encontrada';
    end if;
    update public.representacoes set ativo=false,atualizado_em=now() where id=p_representacao_id;
    for v_cliente in select distinct cliente_id from public.representacao_representados where representacao_id=p_representacao_id and cliente_id is not null loop
        perform private.atualizar_compatibilidade_cliente(v_cliente);
    end loop;
    return jsonb_build_object('schema_version',1,'representacao_id',p_representacao_id::text,'ativo',false);
end;
$function$;

CREATE OR REPLACE FUNCTION public.criar_cliente_para_pessoa_v1(p_pessoa_id uuid, p_dados jsonb, p_chave_app text DEFAULT NULL::text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare
    v_cliente integer;
    v_pessoa public.pessoas_cadastro%rowtype;
    v_pfc public.pessoas_fisicas_cadastro%rowtype;
    v_pjc public.pessoas_juridicas_cadastro%rowtype;
    v_dados jsonb:=coalesce(p_dados,'{}'::jsonb);
    v_pf jsonb;
    v_pj jsonb;
    v_end jsonb;
begin
    perform private.validar_chave_assinaturas(p_chave_app);
    select * into v_pessoa from public.pessoas_cadastro where id=p_pessoa_id and ativo;
    if not found then raise exception 'pessoa nao encontrada'; end if;
    select id into v_cliente from public.clientes where pessoa_id=p_pessoa_id order by id limit 1;
    if v_cliente is not null then return jsonb_build_object('schema_version',1,'cliente_id',v_cliente::text,'pessoa_id',p_pessoa_id::text,'existente',true); end if;

    v_dados:=jsonb_set(v_dados,'{cliente}',coalesce(v_dados->'cliente','{}'::jsonb)||jsonb_build_object('tipo_cliente',v_pessoa.tipo_pessoa,'nome_exibicao',coalesce(nullif(v_dados->'cliente'->>'nome_exibicao',''),v_pessoa.nome_exibicao)),true);
    if v_pessoa.tipo_pessoa='PESSOA_JURIDICA' then
        select * into v_pjc from public.pessoas_juridicas_cadastro where pessoa_id=p_pessoa_id;
        v_pj:=coalesce(to_jsonb(v_pjc),'{}'::jsonb)||coalesce(v_dados->'pessoa_juridica','{}'::jsonb)||jsonb_build_object('razao_social',coalesce(nullif(v_dados->'pessoa_juridica'->>'razao_social',''),v_pessoa.nome_exibicao),'cnpj',coalesce(nullif(v_dados->'pessoa_juridica'->>'cnpj',''),v_pessoa.documento));
        v_dados:=jsonb_set(v_dados,'{pessoa_juridica}',v_pj,true);
    else
        select * into v_pfc from public.pessoas_fisicas_cadastro where pessoa_id=p_pessoa_id;
        v_pf:=coalesce(to_jsonb(v_pfc),'{}'::jsonb)||coalesce(v_dados->'pessoa_fisica','{}'::jsonb)||jsonb_build_object('nome_completo',coalesce(nullif(v_dados->'pessoa_fisica'->>'nome_completo',''),v_pessoa.nome_exibicao),'cpf',coalesce(nullif(v_dados->'pessoa_fisica'->>'cpf',''),v_pessoa.documento));
        v_end:=jsonb_build_object('tipo_endereco',v_pfc.tipo_endereco,'logradouro',v_pfc.logradouro,'uf',v_pfc.uf,'cidade',v_pfc.cidade,'bairro',v_pfc.bairro,'cep',v_pfc.cep,'numero',v_pfc.numero,'complemento',v_pfc.complemento)||coalesce(v_dados->'endereco','{}'::jsonb);
        v_dados:=jsonb_set(v_dados,'{pessoa_fisica}',v_pf,true);
        v_dados:=jsonb_set(v_dados,'{endereco}',v_end,true);
    end if;

    insert into public.clientes(nome,tipo_cliente,nome_exibicao,cpf_cnpj,pessoa_id,criado_em,atualizado_em)
    values(v_pessoa.nome_exibicao,v_pessoa.tipo_pessoa,v_pessoa.nome_exibicao,v_pessoa.documento,p_pessoa_id,now()::text,now()::text) returning id into v_cliente;
    perform public.atualizar_qualificacao_proprietario(v_cliente::text,v_dados,p_chave_app);
    update public.clientes set pessoa_id=p_pessoa_id where id=v_cliente;
    update public.pessoas_fisicas set pessoa_id=p_pessoa_id where cliente_id=v_cliente;
    update public.pessoas_juridicas set pessoa_id=p_pessoa_id where cliente_id=v_cliente;
    return jsonb_build_object('schema_version',1,'cliente_id',v_cliente::text,'pessoa_id',p_pessoa_id::text,'existente',false);
end;
$function$;
