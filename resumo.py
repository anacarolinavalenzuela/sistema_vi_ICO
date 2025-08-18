import streamlit as st
from io import BytesIO
from utils.classificar import classificar_com_cache, normalizar_tipo_documento, mostrar_classificacao_final
from utils.extrair_texto import extrair_texto
from utils.llm import gerar_resumo_padronizado

@st.cache_data(show_spinner="Gerando resumo...")
def gerar_resumo_com_cache(nome_arquivo, texto, tipo):
    """
    Gera um resumo padronizado do texto, com cache para melhorar performance.
    Retorna aviso se texto estiver vazio.
    """
    if not texto or len(texto.strip()) == 0:
        return "⚠️ Texto vazio ou não extraído para este documento."
    return gerar_resumo_padronizado(texto, tipo)


def mostrar_resumo_tipo():
    """
    Exibe resumos para os documentos filtrados pelo tipo confirmado na sessão.
    Usa cache para texto e resumo para evitar múltiplas chamadas à API.
    """
    tipo = st.session_state.get("tipo_para_resumir", None)
    if not tipo:
        st.warning("Nenhum tipo selecionado para resumir.")
        return

    # Obter classificação final confirmada
    classificacoes = st.session_state.get("classificacao_final", {})
    arquivos_selecionados = classificacoes.get(tipo, [])

    if not arquivos_selecionados:
        st.info(f"Nenhum documento do tipo **{tipo}** foi encontrado.")
        return

    # Inicializar cache de textos se ainda não existir
    if "textos_cache" not in st.session_state:
        st.session_state["textos_cache"] = {}

    # Cabeçalho da seção de resumo
    st.markdown(f"""
        <div style="
            background-color: rgba(255, 255, 255, 0.85);
            padding: 20px;
            border-radius: 12px;
            text-align: center;
            color: black;
            ">
            <h1>📑 Resumos do tipo: {tipo}</h1>
        </div>
    """, unsafe_allow_html=True)

    # Para cada arquivo filtrado, gerar e mostrar resumo
    for file in arquivos_selecionados:
        st.markdown("---")
        st.markdown(f"### 📎 {file['nome']}")

        # Usar texto do cache ou extrair se não existir
        if file["nome"] not in st.session_state["textos_cache"]:
            texto = extrair_texto(BytesIO(file["conteudo"]), file["nome"])
            st.session_state["textos_cache"][file["nome"]] = texto
        else:
            texto = st.session_state["textos_cache"][file["nome"]]

        # Gerar resumo com cache
        with st.spinner("Extraindo e resumindo..."):
            resumo = gerar_resumo_com_cache(file["nome"], texto, tipo)
        st.markdown(resumo, unsafe_allow_html=True)

    st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)

    # Botão para voltar ao menu anterior de resumos
    _, col1, _ = st.columns([1.6, 2, 1])
    with col1:
        st.button("Voltar ao menu de resumos", on_click=lambda: st.session_state.update({"page": "resumo"}))



def mostrar_resumo():
    """
    Interface para mostrar resumo geral e permitir selecionar o tipo de documento para resumir.
    Organiza o fluxo em 2 etapas:
    1. Classificar documentos enviados
    2. Selecionar tipo para gerar resumos
    """
    st.markdown("""
        <div style="
            background-color: rgba(255, 255, 255, 0.85);
            padding: 10px;
            border-radius: 12px;
            text-align: center;
            color: black;
            ">
            <h1 style="margin-bottom: 10px;">Resumo dos Documentos</h1>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='margin-top: 50px;'></div>", unsafe_allow_html=True)

    if "uploaded_files" not in st.session_state or not st.session_state.uploaded_files:
        st.warning("Nenhum arquivo foi enviado. Volte à página de Upload.")
        return


    # 1. Classificar documentos
    st.markdown("### Classificação dos arquivos")
    classificacoes = mostrar_classificacao_final()

    st.markdown("<div style='margin-top: 50px;'></div>", unsafe_allow_html=True)

    # 2. Selecionar tipo para resumir
    st.markdown(f"### Escolha o tipo de documento que deseja resumir")

    tipos_disponiveis = list(classificacoes.keys())
    tipo_escolhido = st.selectbox("", tipos_disponiveis)    

    st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)

    _, col1, _ = st.columns([1.6, 2, 1])
    with col1:
        if st.button("Gerar resumos para este tipo", key="gerar_resumo_tipo"):
            # Atualiza estado para ir para página de resumo específico
            st.session_state["tipo_para_resumir"] = tipo_escolhido
            st.session_state["page"] = "resumo_tipo"
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
