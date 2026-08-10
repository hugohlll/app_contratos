import json
from datetime import date, timedelta
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User, Group

from contratos.models import (
    Contrato, Agente, PostoGraduacao, Comissao, Integrante, Empresa, Funcao,
    ControleExecucao, RegistroFatura, OcorrenciaContratual, CalendarioPrestacao
)


class ControleExecucaoTests(TestCase):
    def setUp(self):
        # 1. Usuários e Grupos
        self.group_admin = Group.objects.create(name='Administradores')
        self.group_auditor = Group.objects.create(name='Auditores')

        self.user_auditor = User.objects.create_user(
            username='auditor1', password='password123'
        )
        self.user_auditor.groups.add(self.group_auditor)

        self.user_admin = User.objects.create_superuser(
            username='admin1', password='password123'
        )

        # 2. Dados Basicos (Posto, Agente, Empresa, Contrato, Funcao)
        self.posto = PostoGraduacao.objects.create(sigla='CAP', descricao='Capitão', senioridade=5)
        self.agente = Agente.objects.create(
            nome_completo='João da Silva',
            nome_de_guerra='Silva',
            posto=self.posto,
            saram='1234567',
            cpf='11122233344'
        )
        self.empresa = Empresa.objects.create(
            razao_social='Empresa Teste LTDA',
            cnpj='11222333000199'
        )
        self.funcao = Funcao.objects.create(titulo='Fiscal Titular')

        self.contrato = Contrato.objects.create(
            numero='55/2026',
            objeto='Prestação de serviço de manutenção predial',
            empresa=self.empresa,
            vigencia_inicio=date(2026, 1, 1),
            vigencia_fim=date(2026, 12, 31),
            valor_total=100000.00
        )

        # 3. Comissão de Fiscalização Ativa
        self.comissao = Comissao.objects.create(
            contrato=self.contrato,
            portaria_numero='Portaria 100/2026',
            tipo='FISCALIZACAO',
            ativa=True
        )
        self.integrante = Integrante.objects.create(
            comissao=self.comissao,
            agente=self.agente,
            funcao=self.funcao,
            data_inicio=date(2026, 1, 1),
            portaria_data=date(2026, 1, 1)
        )

    def test_acesso_portal_execucao_publico(self):
        """Testa se as rotas antigas do portal de execução redirecionam para o portal de prestação de contas."""
        response_index = self.client.get(reverse('portal_execucao_index'))
        self.assertEqual(response_index.status_code, 302)
        self.assertEqual(response_index.url, reverse('portal_prestacao_index'))

        response_fiscais = self.client.get(reverse('portal_execucao_fiscais'))
        self.assertEqual(response_fiscais.status_code, 302)
        self.assertEqual(response_fiscais.url, reverse('portal_prestacao_fiscais'))

    def test_preenchimento_formulario_livro_fiscal(self):
        """Testa a submissão completa do formulário do Livro do Fiscal com faturas e ocorrências."""
        url = reverse('formulario_execucao', kwargs={'contrato_id': self.contrato.id})
        response_get = self.client.get(url)
        self.assertEqual(response_get.status_code, 200)
        self.assertContains(response_get, "Livro do Fiscal Digital")

        faturas_payload = [
            {'numero_nf': 'NF-1001', 'valor': 1500.50, 'numero_ob': '2026OB8001'},
            {'numero_nf': 'NF-1002', 'valor': 3200.00, 'numero_ob': '2026OB8002'}
        ]

        ocorrencias_payload = [
            {
                'data': '2026-05-10',
                'tipo': 'reuniao',
                'descricao': 'Reunião de alinhamento mensal de resultados.',
                'acao_fiscal': 'Solicitada readequação no cronograma.',
                'prazo': '5 dias úteis'
            }
        ]

        post_data = {
            'mes_referencia': 5,
            'ano_referencia': 2026,
            'agente': self.agente.id,
            'houve_substituicao': 'sim',
            'substituicao_entrega_formal': 'sim',
            'substituicao_obs': 'Passagem de serviço realizada sem pendências.',
            'confirmacao_siloms_assinatura': 'sim',
            'confirmacao_siloms_vigencia': 'sim',
            'confirmacao_siloms_execucao': 'sim',
            'possibilidade_aditivo': 'na',
            'tratativas_120_dias': 'na',
            'coordenacao_doc_scon': 'sim',
            'garantia_vigente': 'nao',
            'garantia_providencias': 'Notificada a empresa contratada para renovação da garantia bancária.',
            'notas_empenho': '2026NE000123',
            'cronograma_fisico_financeiro': 'conforme',
            'detalhamento_cronograma': 'Execução normal conforme planejado.',
            'imr_aplicado': 'nao',
            'ocorrencias_ativas_empresa': 'nao',
            'necessidade_paai': 'nao',
            'relatorio_ocorrencias': 'Consolidado da reunião mensal.',
            'observacao': 'Tudo conforme as normas.',
            'faturas_json': json.dumps(faturas_payload),
            'ocorrencias_json': json.dumps(ocorrencias_payload)
        }

        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('upload_prestacao', kwargs={'contrato_id': self.contrato.id}))

        # Verificar se salvou no BD
        self.assertEqual(ControleExecucao.objects.count(), 1)
        ctrl = ControleExecucao.objects.first()
        self.assertEqual(ctrl.contrato, self.contrato)
        self.assertEqual(ctrl.agente, self.agente)
        self.assertEqual(ctrl.status, 'entregue')
        self.assertTrue(ctrl.houve_substituicao)
        self.assertEqual(ctrl.garantia_vigente, 'nao')
        self.assertEqual(ctrl.garantia_providencias, 'Notificada a empresa contratada para renovação da garantia bancária.')

        # Verificar faturas relacionadas
        self.assertEqual(ctrl.faturas.count(), 2)
        f1 = ctrl.faturas.first()
        self.assertEqual(f1.numero_nf, "NF-1001")

        # Verificar ocorrências relacionadas
        self.assertEqual(ctrl.ocorrencias.count(), 1)
        oc1 = ctrl.ocorrencias.first()
        self.assertEqual(oc1.tipo, "reuniao")

    def test_workflow_auditoria_aci_status(self):
        """Testa aprovação e pedido de correção da ACI no Livro do Fiscal."""
        ctrl = ControleExecucao.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=5,
            ano_referencia=2026,
            status='entregue'
        )

        # Acesso negado para não autenticado
        url_ok = reverse('alterar_status_execucao', kwargs={'pk': ctrl.id, 'novo_status': 'ok'})
        res_no_auth = self.client.get(url_ok)
        self.assertEqual(res_no_auth.status_code, 302)

        # Aprovação pelo Auditor
        self.client.login(username="auditor1", password="password123")
        res_ok = self.client.get(url_ok)
        self.assertEqual(res_ok.status_code, 302)
        ctrl.refresh_from_db()
        self.assertEqual(ctrl.status, 'ok')

        # Solicitação de correção com justificativa
        url_corr = reverse('alterar_status_execucao', kwargs={'pk': ctrl.id, 'novo_status': 'correcao'})
        res_corr = self.client.post(url_corr, {'justificativa': 'Corrigir valor da fatura.'})
        self.assertEqual(res_corr.status_code, 302)
        ctrl.refresh_from_db()
        self.assertEqual(ctrl.status, 'correcao')
        self.assertEqual(ctrl.apontamentos.count(), 1)
        self.assertEqual(ctrl.apontamentos.first().descricao, 'Corrigir valor da fatura.')

    def test_salvar_calendario_execucao_deadline(self):
        """Testa atualização da data limite de entrega do Livro do Fiscal via AJAX."""
        self.client.login(username="auditor1", password="password123")
        url = reverse('salvar_calendario_prestacao')
        
        payload = json.dumps({
            'ano': 2026,
            'mes': 5,
            'data_entrega': '2026-05-15',
            'data_entrega_execucao': '2026-05-20',
            'data_apresentacao_fiscais': '2026-05-25',
            'data_apresentacao_gestores': '2026-05-28'
        })
        
        res = self.client.post(url, data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['success'])

        cal = CalendarioPrestacao.objects.get(ano=2026, mes=5)
        self.assertEqual(str(cal.data_entrega_execucao), '2026-05-20')

    def test_exportar_execucao_csv(self):
        """Testa exportação em CSV do relatório de controle de execução."""
        ControleExecucao.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=5,
            ano_referencia=2026,
            status='ok'
        )

        self.client.login(username="auditor1", password="password123")
        url = reverse('exportar_execucao_csv')
        res = self.client.get(url, {'mes': 5, 'ano': 2026})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'text/csv; charset=utf-8')
        content = res.content.decode('utf-8-sig')
        self.assertIn("55/2026", content)
        self.assertIn("Conformidade (OK!)", content)

    def test_status_correcao_e_observacao_aci_na_lista_e_formulario(self):
        """Verifica se o status 'correção' e o texto de observação da ACI são exibidos na lista e no formulário."""
        from contratos.models import ApontamentoCorrecaoExecucao
        
        hoje = date.today()
        primeiro_dia_mes_atual = hoje.replace(day=1)
        ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)

        ctrl = ControleExecucao.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=ultimo_dia_mes_anterior.month,
            ano_referencia=ultimo_dia_mes_anterior.year,
            status='correcao'
        )
        ApontamentoCorrecaoExecucao.objects.create(
            controle=ctrl,
            autor=self.user_auditor,
            descricao="Inconsistência nos valores das faturas apresentadas."
        )

        # 1. Verificar na página de upload de prestação do contrato (upload_contrato.html)
        res_upload = self.client.get(reverse('upload_prestacao', kwargs={'contrato_id': self.contrato.id}))
        self.assertEqual(res_upload.status_code, 200)
        self.assertContains(res_upload, "Ajustes Solicitados pela ACI")
        self.assertContains(res_upload, "Inconsistência nos valores das faturas apresentadas.")

        # 2. Verificar no formulário do fiscal (formulario.html)
        url_form = reverse('formulario_execucao', kwargs={'contrato_id': self.contrato.id})
        res_form = self.client.get(url_form)
        self.assertEqual(res_form.status_code, 200)
        self.assertContains(res_form, "Observação / Apontamentos da ACI após Análise")
        self.assertContains(res_form, "Inconsistência nos valores das faturas apresentadas.")

    def test_upload_prestacao_obrigatoriedade_livro_fiscal(self):
        """Testa se o envio da prestação de contas (slides) é bloqueado até que o Livro do Fiscal seja preenchido."""
        url_upload = reverse('upload_prestacao', kwargs={'contrato_id': self.contrato.id})

        # 1. GET na tela sem o Livro do Fiscal preenchido -> execucao_preenchida deve ser False
        res_get = self.client.get(url_upload)
        self.assertEqual(res_get.status_code, 200)
        self.assertFalse(res_get.context['execucao_preenchida'])
        self.assertContains(res_get, "Preenchimento Obrigatório")

        # 2. Tentativa de POST sem Livro do Fiscal -> Bloqueado com mensagem de erro
        from django.core.files.uploadedfile import SimpleUploadedFile
        fake_pdf = SimpleUploadedFile("slides.pdf", b"%PDF-1.4 test pdf content", content_type="application/pdf")
        
        hoje = date.today()
        primeiro_dia_mes_atual = hoje.replace(day=1)
        ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)

        post_data = {
            'mes_referencia': ultimo_dia_mes_anterior.month,
            'ano_referencia': ultimo_dia_mes_anterior.year,
            'agente': self.agente.id,
            'arquivo': fake_pdf
        }

        res_post_bloqueado = self.client.post(url_upload, post_data)
        self.assertEqual(res_post_bloqueado.status_code, 200)
        self.assertContains(res_post_bloqueado, "O preenchimento do Livro do Fiscal é obrigatório")

        # 3. Preencher o Livro do Fiscal e tentar o POST novamente -> Sucesso
        ControleExecucao.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=ultimo_dia_mes_anterior.month,
            ano_referencia=ultimo_dia_mes_anterior.year,
            status='entregue'
        )

        res_get_liberado = self.client.get(url_upload)
        self.assertTrue(res_get_liberado.context['execucao_preenchida'])

        fake_pdf.seek(0)
        res_post_sucesso = self.client.post(url_upload, post_data)
        self.assertEqual(res_post_sucesso.status_code, 302)
        self.assertIn("enviado=1", res_post_sucesso.url)

    def test_exclusao_publica_livro_fiscal(self):
        """Testa a exclusão pública do Livro do Fiscal via portal (com e sem registro existente)."""
        hoje = date.today()
        primeiro_dia_mes_atual = hoje.replace(day=1)
        ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)

        url_upload_esperada = reverse('upload_prestacao', kwargs={'contrato_id': self.contrato.id})

        # 1. Exclusão quando NÃO existe registro → redireciona com mensagem info
        url = reverse('excluir_controle_execucao_publico', kwargs={'contrato_id': self.contrato.id})
        res_sem_registro = self.client.get(url)
        self.assertEqual(res_sem_registro.status_code, 302)
        self.assertEqual(res_sem_registro.url, url_upload_esperada)

        # 2. Criar registro e excluir → deve remover do banco e redirecionar
        ctrl = ControleExecucao.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=ultimo_dia_mes_anterior.month,
            ano_referencia=ultimo_dia_mes_anterior.year,
            status='entregue'
        )
        self.assertEqual(ControleExecucao.objects.count(), 1)

        res_com_registro = self.client.get(url)
        self.assertEqual(res_com_registro.status_code, 302)
        self.assertEqual(res_com_registro.url, url_upload_esperada)
        self.assertEqual(ControleExecucao.objects.count(), 0)

    def test_exclusao_admin_livro_fiscal(self):
        """Testa que apenas administradores conseguem excluir o Livro do Fiscal via painel."""
        ctrl = ControleExecucao.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=5,
            ano_referencia=2026,
            status='entregue'
        )
        url = reverse('excluir_controle_execucao', kwargs={'pk': ctrl.id})

        # 1. Sem login → redireciona para portal_home
        res_no_login = self.client.get(url)
        self.assertEqual(res_no_login.status_code, 302)
        self.assertTrue(ControleExecucao.objects.filter(pk=ctrl.id).exists())

        # 2. Auditor (não admin) → redireciona (user_passes_test falha)
        self.client.login(username='auditor1', password='password123')
        res_auditor = self.client.get(url)
        self.assertEqual(res_auditor.status_code, 302)
        self.assertTrue(ControleExecucao.objects.filter(pk=ctrl.id).exists())

        # 3. Admin → exclusão com sucesso
        self.client.login(username='admin1', password='password123')
        res_admin = self.client.get(url)
        self.assertEqual(res_admin.status_code, 302)
        self.assertFalse(ControleExecucao.objects.filter(pk=ctrl.id).exists())

    def test_visualizacao_somente_leitura_requer_login(self):
        """Testa que a visualização do Livro do Fiscal requer login e exibe dados e apontamentos."""
        from contratos.models import ApontamentoCorrecaoExecucao

        ctrl = ControleExecucao.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=5,
            ano_referencia=2026,
            status='correcao'
        )
        ApontamentoCorrecaoExecucao.objects.create(
            controle=ctrl,
            autor=self.user_auditor,
            descricao="Fatura NF-1001 com valor divergente."
        )

        url = reverse('visualizar_controle_execucao', kwargs={'pk': ctrl.id})

        # 1. Sem login → redireciona
        res_no_login = self.client.get(url)
        self.assertEqual(res_no_login.status_code, 302)

        # 2. Com login → exibe dados e apontamentos
        self.client.login(username='auditor1', password='password123')
        res_ok = self.client.get(url)
        self.assertEqual(res_ok.status_code, 200)
        self.assertEqual(res_ok.context['controle'], ctrl)
        self.assertEqual(res_ok.context['apontamentos'].count(), 1)
        self.assertContains(res_ok, "Fatura NF-1001 com valor divergente.")

    def test_reenvio_formulario_atualiza_sem_duplicar(self):
        """Testa que o reenvio do formulário para o mesmo contrato/mês atualiza o registro existente."""
        hoje = date.today()
        primeiro_dia_mes_atual = hoje.replace(day=1)
        ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
        filtro_mes = ultimo_dia_mes_anterior.month
        filtro_ano = ultimo_dia_mes_anterior.year

        # Criar primeiro registro
        ctrl_original = ControleExecucao.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=filtro_mes,
            ano_referencia=filtro_ano,
            status='entregue',
            observacao='Primeira versão'
        )
        RegistroFatura.objects.create(controle=ctrl_original, numero_nf='NF-OLD', valor=100)
        self.assertEqual(ControleExecucao.objects.count(), 1)
        self.assertEqual(ctrl_original.faturas.count(), 1)

        # Reenviar o formulário (simula edição)
        url = reverse('formulario_execucao', kwargs={'contrato_id': self.contrato.id})
        post_data = {
            'mes_referencia': filtro_mes,
            'ano_referencia': filtro_ano,
            'agente': self.agente.id,
            'houve_substituicao': 'nao',
            'substituicao_entrega_formal': 'na',
            'substituicao_obs': '',
            'confirmacao_siloms_assinatura': 'sim',
            'confirmacao_siloms_vigencia': 'sim',
            'confirmacao_siloms_execucao': 'sim',
            'possibilidade_aditivo': 'na',
            'tratativas_120_dias': 'na',
            'coordenacao_doc_scon': 'sim',
            'notas_empenho': '2026NE999999',
            'cronograma_fisico_financeiro': 'conforme',
            'detalhamento_cronograma': 'Status ok.',
            'imr_aplicado': 'nao',
            'ocorrencias_ativas_empresa': 'nao',
            'necessidade_paai': 'nao',
            'observacao': 'Versão atualizada',
            'faturas_json': json.dumps([{'numero_nf': 'NF-NEW', 'valor': 500, 'numero_ob': 'OB-1'}]),
            'ocorrencias_json': '[]'
        }


        res = self.client.post(url, post_data)
        self.assertEqual(res.status_code, 302)

        # Deve ter atualizado, não duplicado
        self.assertEqual(ControleExecucao.objects.count(), 1)
        ctrl_atualizado = ControleExecucao.objects.first()
        self.assertEqual(ctrl_atualizado.observacao, 'Versão atualizada')

        # Faturas antigas foram substituídas
        self.assertEqual(ctrl_atualizado.faturas.count(), 1)
        self.assertEqual(ctrl_atualizado.faturas.first().numero_nf, 'NF-NEW')

    def test_correcao_sem_justificativa_bloqueada(self):
        """Testa que alterar status para 'correcao' sem justificativa é rejeitado."""
        ctrl = ControleExecucao.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=5,
            ano_referencia=2026,
            status='entregue'
        )

        self.client.login(username='auditor1', password='password123')
        url = reverse('alterar_status_execucao', kwargs={'pk': ctrl.id, 'novo_status': 'correcao'})

        # POST sem justificativa → deve redirecionar sem alterar status
        res = self.client.post(url, {'justificativa': ''})
        self.assertEqual(res.status_code, 302)
        ctrl.refresh_from_db()
        self.assertEqual(ctrl.status, 'entregue')  # Não alterou
        self.assertEqual(ctrl.apontamentos.count(), 0)  # Nenhum apontamento criado

        # GET (sem body) também deve bloquear
        res_get = self.client.get(url)
        self.assertEqual(res_get.status_code, 302)
        ctrl.refresh_from_db()
        self.assertEqual(ctrl.status, 'entregue')

    def test_status_invalido_rejeitado(self):
        """Testa que um status inexistente é rejeitado na alteração do Livro do Fiscal."""
        ctrl = ControleExecucao.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=5,
            ano_referencia=2026,
            status='entregue'
        )

        self.client.login(username='auditor1', password='password123')
        url = reverse('alterar_status_execucao', kwargs={'pk': ctrl.id, 'novo_status': 'invalido'})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 302)
        ctrl.refresh_from_db()
        self.assertEqual(ctrl.status, 'entregue')  # Permanece inalterado

    def test_usuario_sem_permissao_nao_altera_status(self):
        """Testa que um usuário logado sem grupo Auditores não consegue alterar status do Livro."""
        ctrl = ControleExecucao.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=5,
            ano_referencia=2026,
            status='entregue'
        )

        # Criar usuário sem nenhum grupo
        user_normal = User.objects.create_user(username='normal1', password='password123')
        self.client.login(username='normal1', password='password123')

        url = reverse('alterar_status_execucao', kwargs={'pk': ctrl.id, 'novo_status': 'ok'})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 302)
        ctrl.refresh_from_db()
        self.assertEqual(ctrl.status, 'entregue')  # Não alterou

    def test_dashboard_matriz_execucao(self):
        """Testa que o dashboard inclui a matriz de execução contratual no contexto."""
        hoje = date.today()
        primeiro_dia_mes_atual = hoje.replace(day=1)
        ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)

        ControleExecucao.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=ultimo_dia_mes_anterior.month,
            ano_referencia=ultimo_dia_mes_anterior.year,
            status='ok'
        )

        self.client.login(username='auditor1', password='password123')
        res = self.client.get(reverse('dashboard_prestacao'))
        self.assertEqual(res.status_code, 200)

        # Verificar que a chave matriz_execucao existe no contexto
        self.assertIn('matriz_execucao', res.context)
        matriz = res.context['matriz_execucao']
        self.assertTrue(len(matriz) > 0)

        # Verificar que o contrato está na matriz
        contratos_na_matriz = [item['contrato'] for item in matriz]
        self.assertIn(self.contrato, contratos_na_matriz)

        # Verificar que as entregas incluem o status correto
        item = next(i for i in matriz if i['contrato'] == self.contrato)
        statuses = [e['status'] for e in item['entregas']]
        self.assertIn('ok', statuses)
