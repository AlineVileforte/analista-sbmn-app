import streamlit as st
import google.generativeai as genai
import itertools # Para gerar pares de AFOs
import json # Para salvar e carregar o estado, se necessário

# Importações para Firebase (mantidas conforme instrução, mesmo que não usadas para persistência neste exemplo)
# Estas variáveis são fornecidas pelo ambiente Canvas e são essenciais para a inicialização do Firebase.
# Elas permitem que o aplicativo se conecte ao Firestore e gerencie a autenticação do usuário.
# O 'typeof __app_id !== 'undefined' ? __app_id : 'default-app-id'' é um fallback
# caso as variáveis não estejam definidas, o que é útil para testes locais fora do ambiente Canvas.
#from firebase_admin import credentials, initialize_app
#from firebase_admin import firestore
#from firebase_admin import auth

# Variáveis globais fornecidas pelo ambiente Canvas
#appId = typeof __app_id !== 'undefined' ? __app_id : 'default-app-id';
#firebaseConfig = JSON.parse(typeof __firebase_config !== 'undefined' ? __firebase_config : '{}');
#initialAuthToken = typeof __initial_auth_token !== 'undefined' ? __initial_auth_token : '';

# Inicializa o Firebase
# O Firebase é utilizado para gerenciar dados e autenticação de usuários.
# A inicialização é um passo fundamental para que o aplicativo possa interagir
# com os serviços de backend do Google Cloud, como o Firestore para armazenamento de dados.
#if not firebase_admin._apps:
#    cred = credentials.Certificate(firebaseConfig)
#    initialize_app(cred)

#db = firestore.client()
#auth_instance = auth.Client(app=None) # Usar o app padrão

# --- Configuração da API Gemini (como o "ChatGPT" que você mencionou) ---
# A chave da API será carregada de forma segura pelo Streamlit
# O modelo 'gemini-2.0-flash' é um modelo de linguagem grande e rápido,
# ideal para simular o especialista de domínio.
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-2.0-flash')

# --- Variáveis de Estado do Streamlit ---
# st.session_state é como a "memória" do seu aplicativo.
# Ele guarda informações importantes para que o app não "esqueça"
# o que aconteceu entre uma interação e outra do usuário.
if 'fase' not in st.session_state:
    st.session_state.fase = "introducao" # Fase atual da entrevista
if 'nome_processo' not in st.session_state:
    st.session_state.nome_processo = "" # Nome do processo a ser mapeado
if 'dominio_processo' not in st.session_state:
    st.session_state.dominio_processo = "" # Domínio/Setor do processo
if 'afos' not in st.session_state:
    st.session_state.afos = [] # Lista de Atividades e Eventos Iniciais (AFOs)
if 'relacoes' not in st.session_state:
    st.session_state.relacoes = [] # Lista de relações SBMN identificadas (DEP, XOR, etc.)
if 'pares_pendentes' not in st.session_state:
    st.session_state.pares_pendentes = [] # Pares de AFOs que ainda precisam ser questionados
if 'indice_par_atual' not in st.session_state:
    st.session_state.indice_par_atual = 0 # Índice do par de AFOs atual sendo questionado
if 'pergunta_tipo' not in st.session_state:
    st.session_state.pergunta_tipo = "DEP" # Tipo de pergunta SBMN (DEP, XOR, UNI)

# --- Funções Auxiliares ---

def avancar_fase(proxima_fase):
    """
    Função para mudar a fase da entrevista e forçar o Streamlit a atualizar a interface.
    """
    st.session_state.fase = proxima_fase
    st.rerun() # Recarrega a página para mostrar a nova fase

def gerar_proximo_par_e_tipo():
    """
    Lógica para avançar entre os tipos de perguntas (DEP, XOR, UNI) para cada par de AFOs.
    Quando todas as perguntas para um par são feitas, avança para o próximo par.
    """
    if not st.session_state.pares_pendentes:
        st.session_state.fase = "encerramento"
        return None, None, None

    a, b = st.session_state.pares_pendentes[st.session_state.indice_par_atual]

    if st.session_state.pergunta_tipo == "DEP":
        st.session_state.pergunta_tipo = "XOR"
        return a, b, "DEP"
    elif st.session_state.pergunta_tipo == "XOR":
        # Se XOR foi a última pergunta para o par atual, avança para o próximo par
        st.session_state.indice_par_atual += 1
        st.session_state.pergunta_tipo = "DEP" # Reinicia para o próximo par

        # Verifica se ainda há pares antes de tentar acessar
        if st.session_state.indice_par_atual < len(st.session_state.pares_pendentes):
            next_a, next_b = st.session_state.pares_pendentes[st.session_state.indice_par_atual]
            return next_a, next_b, "DEP" # Retorna a primeira pergunta (DEP) para o novo par
        else:
            st.session_state.fase = "encerramento"
            return None, None, None # Não há mais pares, encerra a entrevista

    # Caso chegue aqui sem um tipo definido (não deve acontecer com o fluxo acima)
    st.session_state.fase = "encerramento"
    return None, None, None

def verificar_inconsistencia(relacao, afo1, afo2=None):
    """
    Função de placeholder para verificação de inconsistências SBMN.
    Em um sistema real, esta lógica seria muito mais complexa e robusta,
    envolvendo a análise de um grafo de dependências.
    Aqui, vamos simular uma detecção de DEP e XOR para o mesmo par,
    que é uma inconsistência comum.
    """
    inconsistencias_detectadas = []

    # Exemplo simples: Detecção de DEP e XOR para o mesmo par
    if relacao['tipo'] == 'DEP' and relacao['sua_validacao'] == 'Sim':
        for r in st.session_state.relacoes:
            if r['tipo'] == 'XOR' and r['sua_validacao'] == 'Sim':
                # Verifica se os AFOs são os mesmos, em qualquer ordem
                if (r['afo1'] == afo1 and r['afo2'] == afo2) or \
                   (r['afo1'] == afo2 and r['afo2'] == afo1):
                    inconsistencias_detectadas.append(
                        f"Inconsistência detectada: 'DEP' e 'XOR' para o mesmo par ({afo1}, {afo2}). "
                        "Isso significa que B depende de A E A e B não podem ocorrer juntas. "
                        "Por favor, reavalie a relação."
                    )
                    st.warning(inconsistencias_detectadas[-1])
                    break # Para de verificar após encontrar a primeira inconsistência para este par

    # Você adicionaria mais lógica aqui para outros tipos de inconsistências SBMN
    # (Ex: Ciclos de dependência, Bloqueio de dependência indireta, Promiscuidade, Dependência Dual)

    return inconsistencias_detectadas

def obter_resposta_ia(pergunta_ao_especialista):
    """
    Função para chamar a API do Gemini (LLM) para atuar como o "especialista de domínio".
    Ele vai responder às perguntas SBMN (Sim/Não ou explicação concisa).
    """
    try:
        # O prompt de sistema orienta a IA sobre seu papel
        system_prompt = (
            f"Você é um especialista de domínio do processo '{st.session_state.nome_processo}' "
            f"no setor de '{st.session_state.dominio_processo}'. "
            "Eu farei perguntas sobre dependências e exclusões de tarefas (AFOs). "
            "Responda apenas 'Sim' ou 'Não' quando a pergunta for binária. "
            "Se precisar de mais contexto ou achar a pergunta ambígua, peça esclarecimentos. "
            "Se for uma pergunta aberta, forneça uma resposta concisa."
        )
        
        # Histórico da conversa para manter o contexto
        chat_history = [
            {"role": "user", "parts": [{ "text": system_prompt }]},
            {"role": "model", "parts": [{ "text": "Entendido. Estou pronto para ajudar como especialista de domínio." }]}
        ]
        
        # Adiciona a pergunta atual
        chat_history.append({"role": "user", "parts": [{ "text": pergunta_ao_especialista }]})

        # Faz a chamada à API do Gemini
        response = model.generate_content(chat_history)
        
        # Extrai a resposta do modelo
        resposta_especialista = response.text.strip()
        return resposta_especialista
    except Exception as e:
        st.error(f"Erro ao comunicar com a Inteligência Artificial: {e}")
        return "Erro na comunicação com o especialista."

# --- Interface do Streamlit ---

st.title("Analista de Processos SBMN Virtual")
st.markdown("Seu objetivo é conduzir entrevistas com especialistas de domínio para **capturar e modelar o comportamento de processos de negócio** de forma declarativa e consistente.")

# --- Fase 1: Introdução e Coleta de Dados Iniciais ---
if st.session_state.fase == "introducao":
    st.header("Fase 1: Introdução e Coleta de Dados Iniciais")
    st.write("Olá! Eu sou seu Analista de Processos SBMN. Nossa meta é entender e mapear o processo de negócio para otimizá-lo e gerar modelos BPMN precisos.")

    # Campos de entrada para o usuário (stakeholder)
    nome_proc = st.text_input("1.2. Nome Completo e Descritivo do Processo:", value=st.session_state.nome_processo)
    dominio_proc = st.text_input("1.2. Setor/Domínio de Aplicação do Processo:", value=st.session_state.dominio_processo)
    afos_input = st.text_area("1.3. Liste as principais tarefas e eventos (AFOs), separadas por vírgula:", value=", ".join(st.session_state.afos))

    if st.button("Iniciar Entrevista"):
        if nome_proc and dominio_proc and afos_input:
            st.session_state.nome_processo = nome_proc
            st.session_state.dominio_processo = dominio_proc
            # Processa a lista de AFOs, removendo espaços extras e vazios
            st.session_state.afos = [afo.strip() for afo in afos_input.split(',') if afo.strip()]
            
            if len(st.session_state.afos) < 2:
                st.error("Por favor, liste pelo menos duas AFOs para iniciar as perguntas sobre relações.")
            else:
                # Gera todos os pares possíveis (A, B) para as perguntas de dependência/exclusão
                # itertools.permutations(lista, 2) cria pares ordenados (A,B) e (B,A)
                st.session_state.pares_pendentes = list(itertools.permutations(st.session_state.afos, 2))
                st.session_state.indice_par_atual = 0
                st.session_state.pergunta_tipo = "DEP" # Começa com a primeira pergunta para o primeiro par
                avancar_fase("entrevista") # Avança para a próxima fase
        else:
            st.error("Por favor, preencha todos os campos para iniciar a entrevista.")

# --- Fase 2: Entrevista Baseada em Situações SBMN ---
elif st.session_state.fase == "entrevista":
    st.header("Fase 2: Entrevista Baseada em Situações SBMN")
    st.write(f"**Processo:** {st.session_state.nome_processo} | **Domínio:** {st.session_state.dominio_processo}")
    st.markdown("---")

    # Verifica se ainda há pares de AFOs para questionar
    if st.session_state.indice_par_atual >= len(st.session_state.pares_pendentes):
        st.session_state.fase = "encerramento"
        st.rerun() # Redireciona para a fase de encerramento
    else:
        afo_a, afo_b = st.session_state.pares_pendentes[st.session_state.indice_par_atual]
        pergunta_ao_ia = ""
        tipo_relacao_atual = st.session_state.pergunta_tipo

        # Formula a pergunta com base no tipo de relação SBMN
        if tipo_relacao_atual == "DEP":
            st.subheader("2.1. Dependência Estrita (DEP)")
            pergunta_ao_ia = f"A tarefa '{afo_b}' **depende estritamente** da tarefa '{afo_a}' para ocorrer? Ou seja, '{afo_b}' *só pode* começar se '{afo_a}' tiver sido concluída?"
        elif tipo_relacao_atual == "XOR":
            st.subheader("2.3. Não-Coexistência (XOR)")
            pergunta_ao_ia = f"As tarefas '{afo_a}' e '{afo_b}' **não podem ocorrer juntas** no mesmo fluxo de processo? Elas se excluem mutuamente?"
        # Você pode adicionar a lógica para UNI aqui, seguindo o mesmo padrão:
        # elif tipo_relacao_atual == "UNI":
        #    st.subheader("2.4. União Inclusiva (UNI)")
        #    pergunta_ao_ia = f"Pode ocorrer apenas '{afo_a}', apenas '{afo_b}', ou **ambos** '{afo_a}' e '{afo_b}' no mesmo fluxo de processo? (Ou seja, pelo menos um deles deve ocorrer, mas ambos podem ocorrer)."

        st.write(f"**AFO A:** `{afo_a}` | **AFO B:** `{afo_b}`")
        st.write(pergunta_ao_ia)

        # Chama a IA para obter a resposta do "especialista de domínio"
        with st.spinner("Aguardando resposta do especialista (IA)..."):
            resposta_ia = obter_resposta_ia(pergunta_ao_ia)
        st.info(f"Resposta do Especialista (IA): **{resposta_ia}**")

        st.markdown("---")
        st.subheader("Sua Validação (Analista):")
        # O usuário (você ou o stakeholder) valida a resposta da IA
        sua_resposta = st.radio("Essa resposta do especialista (IA) está correta para o processo real?", 
                                 options=["Sim", "Não"], 
                                 key=f"resp_{afo_a}_{afo_b}_{tipo_relacao_atual}")
        observacao = st.text_area("Observações (opcional, para sua anotação):", 
                                  key=f"obs_{afo_a}_{afo_b}_{tipo_relacao_atual}")

        if st.button("Confirmar e Próxima Pergunta"):
            relacao_registrada = {
                "afo1": afo_a,
                "afo2": afo_b,
                "tipo": tipo_relacao_atual,
                "resposta_ia": resposta_ia,
                "sua_validacao": sua_resposta,
                "observacao": observacao
            }
            
            # Adiciona a relação à lista APENAS se a sua validação for "Sim"
            if sua_resposta == "Sim":
                st.session_state.relacoes.append(relacao_registrada)
                # Verifica inconsistências (simplificado, para demonstração)
                verificar_inconsistencia(relacao_registrada, afo_a, afo_b)

            # Lógica para avançar para a próxima pergunta ou próximo par de AFOs
            if st.session_state.pergunta_tipo == "DEP":
                st.session_state.pergunta_tipo = "XOR"
            elif st.session_state.pergunta_tipo == "XOR":
                st.session_state.indice_par_atual += 1
                st.session_state.pergunta_tipo = "DEP" # Reinicia para o próximo par

            # Verifica se todos os pares foram questionados
            if st.session_state.indice_par_atual >= len(st.session_state.pares_pendentes):
                st.session_state.fase = "encerramento"
            st.rerun() # Recarrega para mostrar a próxima pergunta/fase


# --- Fase 4: Encerramento da Entrevista ---
elif st.session_state.fase == "encerramento":
    st.header("Fase 4: Encerramento da Entrevista")
    st.write("A entrevista foi concluída ou as condições de encerramento foram atingidas.")
    st.write("### Modelo SBMN Mapeado (Relações Validadas por Você):")

    if st.session_state.relacoes:
        for rel in st.session_state.relacoes:
            st.write(f"- `{rel['afo1']}` **{rel['tipo']}** `{rel['afo2']}` (Resposta IA: '{rel['resposta_ia']}', Validado por você: {rel['sua_validacao']})")
            if rel['observacao']:
                st.caption(f"  Obs: {rel['observacao']}")
    else:
        st.info("Nenhuma relação foi validada e registrada durante esta entrevista.")

    st.write("---")
    st.write("### Resumo das Atividades e Eventos Iniciais (AFOs):")
    st.write(", ".join(st.session_state.afos))

    st.write("---")
    if st.button("Reiniciar Entrevista"):
        # Limpa todas as variáveis de estado para começar do zero
        for key in st.session_state.keys():
            del st.session_state[key]
        st.rerun() # Recarrega a página