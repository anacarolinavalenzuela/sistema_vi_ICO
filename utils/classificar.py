import streamlit as st
from openai import OpenAI
import os
import unicodedata
import re
from utils.extrair_texto import extrair_texto
from io import BytesIO
from collections import defaultdict

# ---------------- FUNÇÕES DE CLASSIFICAÇÃO ---------------- #

def criar_cliente_openai():
    api_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY não está configurada no ambiente")
    return OpenAI(api_key=api_key)

def normalizar_texto(texto: str) -> str:
    texto = ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )
    texto = re.sub(r'\s+', ' ', texto)
    return texto.lower().strip()

def eh_parte_de_edital(nome_arquivo: str) -> bool:
    nome_norm = normalizar_texto(nome_arquivo)
    palavras_chave = [
        "edital", "licit", "instrucoes", "instruc", "lista de requerimentos",
        "criterio", "formulario", "modelo de acordo", "secao", "condicoes gerais",
        "questionario"
    ]
    return any(palavra in nome_norm for palavra in palavras_chave)

def normalizar_tipo_documento(tipo: str, nome_arquivo: str = None) -> str:
    tipo_lower = normalizar_texto(tipo)
    
    if "edital de licitacao" in tipo_lower or (nome_arquivo and eh_parte_de_edital(nome_arquivo)):
        return "Edital de Licitação"
    
    mapeamento = {
        "contrato": "Contrato",
        "termo aditivo": "Termo Aditivo",
        "relatório": "Relatório",
        "ofício": "Ofício",
        "ata": "Ata",
        "proposta": "Proposta",
        "minuta": "Minuta",
        "termo de apostilamento": "Termo de Apostilamento",
        "termo de referência": "Termo de Referência",
    }
    
    for chave, valor in mapeamento.items():
        if chave in tipo_lower:
            return valor

    return "Outro"

def classificar_documento(nome_arquivo: str, conteudo_texto: str = None, client=None) -> str:
    if client is None:
        raise ValueError("Client OpenAI deve ser passado para classificar_documento")
    
    if eh_parte_de_edital(nome_arquivo):
        return "Edital de Licitação"
    
    tipos_validos = [
        "Contrato", "Termo Aditivo", "Relatório", "Ofício", "Ata", "Proposta", "Minuta",
        "Termo de Apostilamento", "Edital de Licitação", "Termo de Referência"
    ]

    if conteudo_texto and conteudo_texto.strip():
        prompt = f"""
Classifique o documento com base no conteúdo abaixo.

Lista oficial: {", ".join(tipos_validos)}

Conteúdo:
\"\"\"{conteudo_texto[:4000]}\"\"\"
"""
    else:
        prompt = f"""
Classifique o documento com base apenas no nome do arquivo.

Lista oficial: {", ".join(tipos_validos)}

Nome do arquivo: '{nome_arquivo}'
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=30
    )

    tipo_cru_raw = response.choices[0].message.content.strip()
    tipo_normalizado = normalizar_tipo_documento(tipo_cru_raw, nome_arquivo)

    if tipo_normalizado == "Outro" and tipo_cru_raw.lower() not in [t.lower() for t in tipos_validos]:
        return tipo_cru_raw.title()

    return tipo_normalizado

@st.cache_data(show_spinner="Classificando os documentos...")
def classificar_com_cache(lista_docs):
    client = criar_cliente_openai()
    resultados = []
    for doc in lista_docs:
        classificacao = classificar_documento(doc["nome"], doc.get("conteudo", ""), client=client)
        resultados.append({"nome": doc["nome"], "classificacao": classificacao})
    return resultados

def mostrar_classificacao_documentos():
    """
    Mostra a classificação automática dos documentos, permite ajustes manuais
    e retorna um dicionário com documentos organizados por tipo (somente os confirmados).
    """
    st.markdown("### Classificação automática dos arquivos")

    if "uploaded_files" not in st.session_state or not st.session_state.uploaded_files:
        st.warning("Nenhum arquivo foi enviado. Volte à página de Upload.")
        return

    documentos = st.session_state.get("uploaded_files", [])

    if "docs" not in st.session_state:
        st.session_state.docs = []
        client = criar_cliente_openai()
        for arq in documentos:
            texto = extrair_texto(BytesIO(arq["content"]), arq["name"])
            tipo = normalizar_tipo_documento(classificar_documento(arq["name"], texto, client), arq["name"])
            st.session_state.docs.append({
                "nome": arq["name"],
                "conteudo": arq["content"],
                "classificacao": tipo,
                "confirmado": False  # flag para rastrear confirmação
            })

    if "modo_ajuste" not in st.session_state:
        st.session_state.modo_ajuste = False

    # Agrupar documentos por classificação
    classificacoes = defaultdict(list)
    for doc in st.session_state.docs:
        classificacoes[doc['classificacao']].append(doc['nome'])

    # Criar um expander para cada classificação
    for tipo, arquivos in classificacoes.items():
        with st.expander(f"{tipo} ({len(arquivos)} arquivo(s))"):
            for nome in arquivos:
                st.markdown(f"- {nome}")

    # Botões principais
    col_esq, col_btn1, col_espaco, col_btn2, col_dir = st.columns([1.2, 1.7, 0.1, 2, 1])

    # Continuar: confirma todos os documentos
    with col_btn1:
        if st.button("Continuar", key="btn_continuar"):
            for d in st.session_state.docs:
                d["confirmado"] = True

            # Agrupamento corrigido
            st.session_state["classificacao_final"] = {
                tipo: [doc for doc in st.session_state.docs if doc["classificacao"] == tipo and doc.get("confirmado", False)]
                for tipo in set(d["classificacao"] for d in st.session_state.docs)
            }

            st.session_state["page"] = "menu"
            st.rerun()

    # Ajustar classificações
    with col_btn2:
        if st.button("Ajustar classificações", key="btn_ajustar"):
            st.session_state.modo_ajuste = True

    st.markdown("<div style='margin-top: 50px;'></div>", unsafe_allow_html=True)

    # Modo de ajuste
    if st.session_state.modo_ajuste:
        st.markdown("### Ajustar classificação dos arquivos")
        nomes_docs = [doc["nome"] for doc in st.session_state.docs]
        doc_escolhido = st.selectbox("", nomes_docs)

        tipos_opcoes = [
            "Contrato", "Termo Aditivo", "Relatório", "Ofício", "Ata", "Proposta",
            "Minuta", "Termo de Apostilamento", "Edital de Licitação", "Termo de Referência", "Outro"
        ]

        classificacao_atual = next(d["classificacao"] for d in st.session_state.docs if d["nome"] == doc_escolhido)
        nova_classificacao = st.selectbox(
            "",
            tipos_opcoes,
            index=tipos_opcoes.index(classificacao_atual) if classificacao_atual in tipos_opcoes else len(tipos_opcoes)-1
        )

        if nova_classificacao == "Outro":
            nova_classificacao = st.text_input("Especifique o tipo:")

        # Aplicar ajuste
        _, col1, _ = st.columns([0.7, 1, 0.3])
        with col1:
            if st.button("Aplicar ajuste", key="btn_aplicar_ajuste"):
                for d in st.session_state.docs:
                    if d["nome"] == doc_escolhido:
                        d["classificacao"] = nova_classificacao
                st.success(f"Classificação de **{doc_escolhido}** atualizada para **{nova_classificacao}**")

        # Finalizar ajustes: confirma os documentos
        _, col1, _ = st.columns([0.7, 1, 0.3])
        with col1:
            if st.button("Finalizar ajustes", key="btn_finalizar_ajustes"):
                for d in st.session_state.docs:
                    if not d.get("confirmado", False):
                        d["confirmado"] = True  # garante que todos entrem na classificação final

                # Agrupamento corrigido
                st.session_state["classificacao_final"] = {
                    tipo: [doc for doc in st.session_state.docs if doc["classificacao"] == tipo and doc.get("confirmado", False)]
                    for tipo in set(d["classificacao"] for d in st.session_state.docs)
                }

                st.session_state.modo_ajuste = False
                st.session_state["page"] = "menu"
                st.rerun()

    # Organiza documentos confirmados por tipo e retorna
    classificacoes = {}
    for doc in st.session_state.docs:
        if not doc.get("confirmado", False):
            continue
        tipo = doc["classificacao"]
        if tipo not in classificacoes:
            classificacoes[tipo] = []
        classificacoes[tipo].append(doc)

    return classificacoes


def mostrar_classificacao_final():
    """
    Mostra a classificação final confirmada pelo usuário em um expander.
    Retorna um dicionário com tipos de documento e os arquivos correspondentes.
    """
    if "classificacao_final" not in st.session_state:
        st.warning("Nenhuma classificação final encontrada. Volte à página de classificação.")
        return {}

    classificacoes = st.session_state["classificacao_final"]

    for tipo, arquivos in classificacoes.items():
        with st.expander(f"{tipo} ({len(arquivos)} arquivo(s))"):
            for file in arquivos:
                st.markdown(f"- {file['nome']}")

    return classificacoes


