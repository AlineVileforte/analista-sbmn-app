import streamlit as st
import google.generativeai as genai
import itertools # Para gerar pares de AFOs
import json # Para salvar e carregar o estado, se necessário

# --- Configuração da API Gemini ---
# A chave da API será carregada de forma segura pelo Streamlit
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
    st.session_state.relacoes = [] # Lista de relações SBMN identificadas (DEP, DEPC, XOR, UNI)
if 'pares_pendentes' not in st.session_state:
    st.session_state.pares_pendentes = [] # Pares de AFOs que ainda precisam ser questionados (tuplas: AFO_A, AFO_B)
if 'indice_par_atual' not in st.session_state:
    st.session_state.indice_par_atual = 0 # Índice do par de AFOs atual sendo questionado
if 'pergunta_tipo' not in st.session_state:
    st.session_state.pergunta_tipo = "DEP_INICIAL" # Tipo de pergunta SBMN (DEP_INICIAL, DEP_COMPLEMENTAR, XOR, UNI)
if 'resposta_dep_inicial' not in st.session_state:
    st.session_state.resposta_dep_inicial = None # Para armazenar a resposta da primeira pergunta de DEP e decidir se DEPC é feita
# Variáveis de estado para as checkboxes da UNI
if 'uni_apenas_a_ocorre' not in st.session_state:
    st.session_state.uni_apenas_a_ocorre = False
if 'uni_apenas_b_ocorre' not in st.session_state:
    st.session_state.uni_apenas_b_ocorre = False
if 'uni_ambos_ocorrem' not in st.session_state:
    st.session_state.uni_ambos_ocorrem = False


# --- Funções Auxiliares ---

def avancar_fase(proxima_fase):
    """
    Função para mudar a fase da entrevista e forçar o Streamlit a atualizar a interface.
    """
    st.session_state.fase = proxima_fase
    st.rerun() # Recarrega a página para mostrar a nova fase

def avancar_pergunta_sbm_para_proximo_par():
    """
    Controla o fluxo das perguntas SBMN (DEP_INICIAL, DEP_COMPLEMENTAR, XOR, UNI)
    e avança para o próximo par de AFOs quando todas as perguntas são feitas.
    """
    # Resetar os estados das checkboxes da UNI para o próximo par
    st.session_state.uni_apenas_a_ocorre = False
    st.session_state.uni_apenas_b_ocorre = False
    st.session_state.uni_ambos_ocorrem = False

    if st.session_state.pergunta_tipo == "DEP_INICIAL":
        if st.session_state.resposta_dep_inicial == "Sim":
            st.session_state.pergunta_tipo = "DEP_COMPLEMENTAR"
        else: # Respondeu "Não" para a DEP_INICIAL, então não há DEPC. Vai direto para XOR.
            st.session_state.pergunta_tipo = "XOR"
    elif st.session_state.pergunta_tipo == "DEP_COMPLEMENTAR":
        st.session_state.pergunta_tipo = "XOR"
    elif st.session_state.pergunta_tipo == "XOR":
        st.session_state.pergunta_tipo = "UNI"
    elif st.session_state.pergunta_tipo == "UNI":
        # Todas as perguntas para o par atual foram feitas, avança para o próximo par
        st.session_state.indice_par_atual += 1
        st.session_state.pergunta_tipo = "DEP_INICIAL" # Reinicia o ciclo de perguntas para o novo par
        st.session_state.resposta_dep_inicial = None # Reset para o novo par

    # Verifica se ainda há pares antes de tentar acessar
    if st.session_state.indice_par_atual >= len(st.session_state.pares_pendentes):
        st.session_state.fase = "encerramento"
        st.rerun()

def verificar_inconsistencia(relacao):
    """
    Função de placeholder para verificação de inconsistências SBMN.
    Em um sistema real, esta lógica seria muito mais complexa e robusta,
    envolvendo a análise de um grafo de dependências.
    Aqui, vamos simular uma detecção de DEP (estrita) e XOR para o mesmo par,
    que é uma inconsistência comum.
    """
    afo1 = relacao['afo1']
    afo2 = relacao['afo2']
    tipo = relacao['tipo']
    resposta_validada = relacao['sua_validacao']

    # Exemplo simples: Detecção de DEP e XOR para o mesmo par (Equivalent Operators)
    # Se uma DEP estrita foi validada E uma XOR também foi validada para o mesmo par.
    if resposta_validada == "Sim":
        if tipo == 'DEP': 
            for r in st.session_state.relacoes:
                # Verifica se a relação existente é XOR e foi validada como Sim
                if r['tipo'] == 'XOR' and r['sua_validacao'] == 'Não': # 'Não' para "podem ocorrer juntas?" significa que É XOR.
                    # Verifica se os AFOs são os mesmos, em qualquer ordem
                    if (r['afo1'] == afo1 and r['afo2'] == afo2) or \
                       (r['afo1'] == afo2 and r['afo2'] == afo1):
                        st.warning(
                            f"**Inconsistência detectada (Equivalent Operators):** "
                            f"As tarefas '{afo1}' e '{afo2}' possuem uma Dependência Estrita E uma Não-Coexistência (XOR). "
                            "Isso significa que uma depende da outra E elas não podem ocorrer juntas, o que é contraditório. "
                            "Por favor, reavalie a relação para esse par."
                        )
                        break
        elif tipo == 'XOR': # Se uma XOR foi validada E uma DEP estrita também foi validada para o mesmo par.
             for r in st.session_state.relacoes:
                # Verifica se a relação existente é DEP e foi validada como Sim
                if r['tipo'] == 'DEP' and r['sua_validacao'] == 'Sim': 
                    # Verifica se os AFOs são os mesmos, em qualquer ordem
                    if (r['afo1'] == afo1 and r['afo2'] == afo2) or \
                       (r['afo1'] == afo2 and r['afo2'] == afo1):
                        st.warning(
                            f"**Inconsistência detectada (Equivalent Operators):** "
                            f"As tarefas '{afo1}' e '{afo2}' possuem uma Dependência Estrita E uma Não-Coexistência (XOR). "
                            "Isso significa que uma depende da outra E elas não podem ocorrer juntas, o que é contraditório. "
                            "Por favor, reavalie a relação para esse par."
                        )
                        break

    # Você adicionaria mais lógica aqui para outros tipos de inconsistências SBMN
    # (Ex: Ciclos de dependência, Bloqueio de dependência indireta, Promiscuidade, Dependência Dual)

def obter_resposta_ia(pergunta_ao_especialista, tipo_pergunta_sbm):
    """
    Função para chamar a API do Gemini (LLM) para atuar como o "especialista de domínio".
    Ele vai responder às perguntas SBMN (Sim/Não ou explicação concisa para UNI).
    """
    try:
        # O prompt de sistema orienta a IA sobre seu papel
        system_prompt = (
            f"Você é um especialista de domínio do processo '{st.session_state.nome_processo}' "
            f"no setor de '{st.session_state.dominio_processo}'. "
            "Eu farei perguntas sobre dependências e exclusões de tarefas (AFOs) para modelar um processo. "
        )
        
        # Ajusta a instrução para a IA dependendo do tipo de pergunta
        if tipo_pergunta_sbm == "UNI":
            # Para UNI, a IA deve responder com uma combinação das opções
            system_prompt += "Para a próxima pergunta, você deve responder indicando quais das opções são possíveis: 'apenas A', 'apenas B', 'ambos A e B', ou uma combinação dessa (por exemplo, 'apenas A e ambos')."
        else:
            # Para DEP e XOR, a IA deve responder Sim ou Não
            system_prompt += "Responda apenas 'Sim' ou 'Não' quando a pergunta for binária. Se precisar de mais contexto ou achar a pergunta ambígua, peça esclarecimentos."
        
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
st.markdown("Seu objetivo principal é conduzir entrevistas com especialistas de domínio para **capturar e modelar o comportamento de processos de negócio** de forma declarativa e consistente, visando a futura derivação de modelos BPMN executáveis e otimizados.")

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
                st.session_state.pergunta_tipo = "DEP_INICIAL" # Começa com a primeira pergunta para o primeiro par
                st.session_state.resposta_dep_inicial = None # Reseta a resposta inicial da DEP
                avancar_fase("entrevista") # Avança para a próxima fase
        else:
            st.error("Por favor, preencha todos os campos para iniciar a entrevista.")

# --- Fase 2: Entrevista Baseada em Situações SBMN ---
elif st.session_state.fase == "entrevista":
    st.header("Fase 2: Entrevista Baseada em Situações SBMN (Coleta de Restrições Declarativas)")
    st.write(f"**Processo:** {st.session_state.nome_processo} | **Domínio:** {st.session_state.dominio_processo}")
    st.markdown("---")

    # Verifica se ainda há pares de AFOs para questionar
    if st.session_state.indice_par_atual >= len(st.session_state.pares_pendentes):
        st.session_state.fase = "encerramento"
        st.rerun() # Redireciona para a fase de encerramento
    else:
        afo_a, afo_b = st.session_state.pares_pendentes[st.session_state.indice_par_atual]
        pergunta_ao_ia = ""
        tipo_relacao_actual = st.session_state.pergunta_tipo

        st.write(f"**Analisando o par:** `{afo_a}` e `{afo_b}`")

        # Formula a pergunta com base no tipo de relação SBMN
        if tipo_relacao_actual == "DEP_INICIAL":
            st.subheader("2.1. Verificação de Dependência com Classificação (Pergunta Inicial)")
            pergunta_ao_ia = f"A tarefa '{afo_b}' depende de '{afo_a}' para ocorrer?"
        elif tipo_relacao_actual == "DEP_COMPLEMENTAR":
            st.subheader("2.1. Verificação de Dependência com Classificação (Pergunta Complementar)")
            pergunta_ao_ia = f"Essa dependência é obrigatória? Ou seja, '{afo_b}' só pode começar se '{afo_a}' tiver ocorrido?"
        elif tipo_relacao_actual == "XOR":
            st.subheader("2.3. Não-Coexistência (XOR)")
            pergunta_ao_ia = f"As tarefas '{afo_a}' e '{afo_b}' **podem ocorrer juntas** no mesmo fluxo de processo?"
        elif tipo_relacao_actual == "UNI":
            st.subheader("2.4. União Inclusiva (UNI)")
            pergunta_ao_ia = (
                f"Considerando as tarefas '{afo_a}' e '{afo_b}', por favor, me diga qual (ou quais) das seguintes situações são possíveis neste processo: \n"
                f"- Apenas '{afo_a}' ocorre \n"
                f"- Apenas '{afo_b}' ocorre \n"
                f"- Ambos '{afo_a}' e '{afo_b}' ocorrem"
            )
            # A instrução para a IA fica no `obter_resposta_ia`, aqui para o usuário, podemos ser mais diretos.
            # st.caption("Você pode me dizer 'apenas A', 'apenas B', 'ambos', ou uma combinação delas (ex: 'apenas A e ambos').")

        st.write(pergunta_ao_ia)

        # Chama a IA para obter a resposta do "especialista de domínio"
        with st.spinner("Aguardando resposta do especialista (IA)..."):
            resposta_ia = obter_resposta_ia(pergunta_ao_ia, tipo_relacao_actual)
        st.info(f"Resposta do Especialista (IA): **{resposta_ia}**")

        st.markdown("---")
        st.subheader("Sua Validação (Analista):")
        
        # --- MODIFICAÇÃO AQUI: Pergunta UNI com Checkboxes ---
        if tipo_relacao_actual == "UNI":
            st.markdown("Por favor, confirme as opções que são válidas para o processo:")
            st.session_state.uni_apenas_a_ocorre = st.checkbox(f"Apenas '{afo_a}' ocorre", key=f"check_a_{afo_a}_{afo_b}", 
                                                               value=st.session_state.uni_apenas_a_ocorre)
            st.session_state.uni_apenas_b_ocorre = st.checkbox(f"Apenas '{afo_b}' ocorre", key=f"check_b_{afo_a}_{afo_b}",
                                                               value=st.session_state.uni_apenas_b_ocorre)
            st.session_state.uni_ambos_ocorrem = st.checkbox(f"Ambos '{afo_a}' e '{afo_b}' ocorrem", key=f"check_ambos_{afo_a}_{afo_b}",
                                                              value=st.session_state.uni_ambos_ocorrem)
            
            # A resposta para registro será construída a partir do estado das checkboxes
            resposta_para_registro = []
            if st.session_state.uni_apenas_a_ocorre:
                resposta_para_registro.append(f"Apenas {afo_a}")
            if st.session_state.uni_apenas_b_ocorre:
                resposta_para_registro.append(f"Apenas {afo_b}")
            if st.session_state.uni_ambos_ocorrem:
                resposta_para_registro.append(f"Ambos {afo_a} e {afo_b}")
            
            # Converte a lista para uma string para armazenamento
            resposta_para_registro = ", ".join(resposta_para_registro) if resposta_para_registro else "Nenhuma das opções selecionadas"

        else: # Para DEP e XOR, mantém o radio button
            sua_resposta_validacao = st.radio("Essa resposta do especialista (IA) está correta para o processo real?", 
                                                 options=["Sim", "Não"], 
                                                 key=f"resp_bin_{afo_a}_{afo_b}_{tipo_relacao_actual}")
            resposta_para_registro = sua_resposta_validacao # "Sim" ou "Não"

        observacao = st.text_area("Observações (opcional, para sua anotação):", 
                                  key=f"obs_{afo_a}_{afo_b}_{tipo_relacao_actual}")

        if st.button("Confirmar e Próxima Pergunta"):
            relacao_registrada = {
                "afo1": afo_a,
                "afo2": afo_b,
                "tipo": "", # O tipo SBMN será classificado abaixo
                "resposta_ia": resposta_ia,
                "sua_validacao": resposta_para_registro, # A string construída das checkboxes ou Sim/Não
                "observacao": observacao
            }
            
            # Lógica para classificar o tipo de relação SBMN e registrar
            if tipo_relacao_actual == "DEP_INICIAL":
                st.session_state.resposta_dep_inicial = resposta_para_registro # Armazena a resposta para a próxima etapa
                if resposta_para_registro == "Não":
                    relacao_registrada["tipo"] = "SEM_DEPENDÊNCIA"
                    st.session_state.relacoes.append(relacao_registrada)
            elif tipo_relacao_actual == "DEP_COMPLEMENTAR":
                if resposta_para_registro == "Sim":
                    relacao_registrada["tipo"] = "DEP" # Dependência Estrita
                else:
                    relacao_registrada["tipo"] = "DEPC" # Dependência Circunstancial
                st.session_state.relacoes.append(relacao_registrada)
                verificar_inconsistencia(relacao_registrada) # Verifica inconsistências após registrar DEP/DEPC
            elif tipo_relacao_actual == "XOR":
                # 'Sim' para "podem ocorrer juntas?" significa que NÃO é XOR.
                # 'Não' para "podem ocorrer juntas?" significa que É XOR.
                if resposta_para_registro == "Não": 
                    relacao_registrada["tipo"] = "XOR"
                else: 
                    relacao_registrada["tipo"] = "NÃO_XOR" # AFOs podem coexistir
                st.session_state.relacoes.append(relacao_registrada)
                verificar_inconsistencia(relacao_registrada) # Verifica inconsistências após registrar XOR
            elif tipo_relacao_actual == "UNI":
                # A classificação da UNI agora depende do estado das checkboxes
                if st.session_state.uni_apenas_a_ocorre and st.session_state.uni_apenas_b_ocorre and st.session_state.uni_ambos_ocorrem:
                    relacao_registrada["tipo"] = "UNI"
                else:
                    relacao_registrada["tipo"] = "NÃO_UNI" # Não é uma UNI completa
                st.session_state.relacoes.append(relacao_registrada)

            avancar_pergunta_sbm_para_proximo_par()
            st.rerun() # Recarrega para mostrar a próxima pergunta/fase


# --- Fase 4: Encerramento da Entrevista ---
elif st.session_state.fase == "encerramento":
    st.header("Fase 4: Encerramento da Entrevista")
    st.write("A entrevista foi concluída ou as condições de encerramento foram atingidas.")
    
    st.write("### Modelo SBMN Mapeado (Relações Validadas por Você):")
    if st.session_state.relacoes:
        for rel in st.session_state.relacoes:
            tipo_display = rel['tipo'] # O tipo já vem classificado
            
            st.write(f"- `{rel['afo1']}` **{tipo_display}** `{rel['afo2']}` (Resposta IA: '{rel['resposta_ia']}', Validado por você: '{rel['sua_validacao']}')")
            if rel['observacao']:
                st.caption(f"  Obs: {rel['observacao']}")
    else:
        st.info("Nenhuma relação foi validada e registrada durante esta entrevista.")

    st.write("---")
    st.write("### Resumo das Atividades e Eventos Iniciais (AFOs):")
    st.write(", ".join(st.session_state.afos))

    st.write("---")
    st.subheader("4.2. Confirmação Final:")
    final_confirm = st.text_area("Há mais alguma atividade, evento ou restrição importante que devemos considerar para este processo?")
    st.write(f"Sua resposta: {final_confirm}")

    if st.button("Reiniciar Entrevista"):
        # Limpa todas as variáveis de estado para começar do zero
        for key in st.session_state.keys():
            del st.session_state[key]
        st.rerun() # Recarrega a página