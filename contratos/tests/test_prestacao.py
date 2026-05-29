import os
from datetime import date
from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.contrib.auth.models import User

from contratos.models import Contrato, Empresa, PrestacaoContas, Agente, PostoGraduacao, Comissao, Integrante, Funcao

class PrestacaoContasTests(TestCase):
    def setUp(self):
        # Configurar ambiente de teste
        self.posto = PostoGraduacao.objects.create(sigla="SGT", descricao="Sargento", senioridade=5)
        self.empresa = Empresa.objects.create(razao_social="Empresa Teste Ltda", cnpj="12345678000199")
        self.agente = Agente.objects.create(
            nome_completo="Joao Silva", 
            nome_de_guerra="Silva", 
            posto=self.posto, 
            saram="1234567"
        )
        self.contrato = Contrato.objects.create(
            numero="10/2026",
            objeto="Serviços de Teste",
            empresa=self.empresa,
            vigencia_inicio=date(2026, 1, 1),
            vigencia_fim=date(2026, 12, 31),
            valor_total=1000.00
        )
        
        # Adicionar o agente a uma comissão ativa
        self.comissao = Comissao.objects.create(
            contrato=self.contrato,
            tipo='FISCALIZACAO',
            ativa=True,
            data_inicio=date(2026, 1, 1)
        )
        self.funcao = Funcao.objects.create(titulo="Fiscal", ordem=1)
        self.integrante = Integrante.objects.create(
            comissao=self.comissao,
            agente=self.agente,
            funcao=self.funcao,
            data_inicio=date(2026, 1, 1),
            portaria_numero="123",
            portaria_data=date(2026, 1, 1)
        )
        
        self.user = User.objects.create_user(username="admin", password="password123")
        self.client = Client()

    def test_upload_prestacao_sem_login(self):
        """O Fical deve conseguir enviar o PDF via formulário público sem estar logado"""
        url = reverse('upload_prestacao', kwargs={'contrato_id': self.contrato.id})
        
        # Simula arquivo PDF válido
        pdf_file = SimpleUploadedFile(
            "teste.pdf",
            b"%PDF-1.4...",
            content_type="application/pdf"
        )
        
        data = {
            'agente': self.agente.id,
            'mes_referencia': 5,
            'ano_referencia': 2026,
            'arquivo': pdf_file,
            'observacao': 'Teste envio'
        }
        
        response = self.client.post(url, data)
        
        # Após salvar deve redirecionar para detalhe_contrato com param ?enviado=1
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith("?enviado=1"))
        
        # Verificar se salvou no BD
        self.assertEqual(PrestacaoContas.objects.count(), 1)
        prestacao = PrestacaoContas.objects.first()
        self.assertEqual(prestacao.mes_referencia, 5)
        self.assertEqual(prestacao.ano_referencia, 2026)
        
        # Verificar renomeação do arquivo
        self.assertTrue(prestacao.arquivo.name.startswith("prestacoes/sgt_silva_empresa-teste-ltda_10-2026_05-2026"))
        self.assertTrue(prestacao.arquivo.name.endswith(".pdf"))
        
        # Limpar arquivo gerado no teste
        if prestacao.arquivo and os.path.isfile(prestacao.arquivo.path):
            os.remove(prestacao.arquivo.path)

    def test_upload_substituicao_mesmo_mes(self):
        """O reenvio para o mesmo contrato, ano e mês cria um novo registro e mantém o anterior"""
        # Upload 1
        pdf_file1 = SimpleUploadedFile("arq1.pdf", b"conteudo1", content_type="application/pdf")
        p1 = PrestacaoContas.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=6,
            ano_referencia=2026,
            arquivo=pdf_file1
        )
        self.assertEqual(PrestacaoContas.objects.count(), 1)
        
        # Upload 2 (POST request para simular substituição da view)
        url = reverse('upload_prestacao', kwargs={'contrato_id': self.contrato.id})
        pdf_file2 = SimpleUploadedFile("arq2.pdf", b"conteudo2", content_type="application/pdf")
        
        data = {
            'agente': self.agente.id,
            'mes_referencia': 6,
            'ano_referencia': 2026,
            'arquivo': pdf_file2,
            'observacao': 'Nova versao'
        }
        
        self.client.post(url, data)
        
        # Deve agora ter 2 registros no banco
        self.assertEqual(PrestacaoContas.objects.count(), 2)
        prestacao = PrestacaoContas.objects.order_by('-data_envio').first()
        self.assertEqual(prestacao.observacao, 'Nova versao')
        
        # Limpeza
        for p in PrestacaoContas.objects.all():
            if p.arquivo and os.path.isfile(p.arquivo.path):
                os.remove(p.arquivo.path)

    def test_dashboard_requer_login(self):
        """Dashboard gerencial deve estar protegido"""
        url = reverse('dashboard_prestacao')
        response = self.client.get(url)
        # Redireciona para login
        self.assertEqual(response.status_code, 302)
        
        # Login
        self.client.login(username="admin", password="password123")
        response2 = self.client.get(url)
        # Sucesso
        self.assertEqual(response2.status_code, 200)

    def test_exportar_prestacao_csv(self):
        """Testa a exportação das prestações de contas (entregues e pendentes) filtradas por mês/ano"""
        # Criar uma prestação de contas no mês 5 de 2026 com status default (entregue)
        pdf_file = SimpleUploadedFile("arq_teste.pdf", b"pdf_data", content_type="application/pdf")
        prestacao = PrestacaoContas.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=5,
            ano_referencia=2026,
            arquivo=pdf_file
        )

        self.client.login(username="admin", password="password123")
        url = reverse('exportar_prestacao_csv')
        
        # Testar exportação para o mês 5 de 2026 (deve ter a prestação como Entregue)
        response = self.client.get(url, {'mes': 5, 'ano': 2026, 'formato': 'csv'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        
        # O CSV é delimitado por ';'
        content = response.content.decode('utf-8-sig')
        lines = content.split('\r\n')
        
        # Verificar cabeçalhos
        headers = lines[0].split(';')
        self.assertIn('Contrato', headers)
        self.assertIn('Situação', headers)
        self.assertIn('Responsável pela Entrega', headers)
        
        # Verificar que o contrato 10/2026 está listado como Entregue pelo agente SGT Silva
        found_entregue = False
        for line in lines[1:]:
            if not line:
                continue
            cols = line.split(';')
            if cols[0] == "10/2026":
                self.assertEqual(cols[9], "Entregue") # Coluna 9 é Situação
                self.assertEqual(cols[10], "SGT Silva") # Coluna 10 é Responsável pela Entrega
                found_entregue = True
                
        self.assertTrue(found_entregue)

        # Atualizar status para 'ok' (Conformidade (OK!)) e exportar novamente
        prestacao.status = 'ok'
        prestacao.save()
        
        response_ok = self.client.get(url, {'mes': 5, 'ano': 2026, 'formato': 'csv'})
        content_ok = response_ok.content.decode('utf-8-sig')
        lines_ok = content_ok.split('\r\n')
        found_ok = False
        for line in lines_ok[1:]:
            if not line:
                continue
            cols = line.split(';')
            if cols[0] == "10/2026":
                self.assertEqual(cols[9], "Conformidade (OK!)")
                found_ok = True
        self.assertTrue(found_ok)

        # Testar exportação para outro mês (por exemplo, mês 6 de 2026) onde não há prestação (deve constar como Pendente)
        response_pending = self.client.get(url, {'mes': 6, 'ano': 2026, 'formato': 'csv'})
        self.assertEqual(response_pending.status_code, 200)
        content_pending = response_pending.content.decode('utf-8-sig')
        lines_pending = content_pending.split('\r\n')
        
        found_pending = False
        for line in lines_pending[1:]:
            if not line:
                continue
            cols = line.split(';')
            if cols[0] == "10/2026":
                self.assertEqual(cols[9], "Pendente")
                self.assertEqual(cols[10], "-")
                found_pending = True
        self.assertTrue(found_pending)

        # Limpar arquivo gerado no teste
        if prestacao.arquivo and os.path.isfile(prestacao.arquivo.path):
            os.remove(prestacao.arquivo.path)

    def test_exportar_prestacao_csv_com_multiplos_envios_exibe_ultimo(self):
        """Exportação mensal deve exibir apenas o último envio quando há múltiplos para o mesmo período."""
        url_upload = reverse('upload_prestacao', kwargs={'contrato_id': self.contrato.id})

        # Primeiro envio
        self.client.post(url_upload, {
            'agente': self.agente.id,
            'mes_referencia': 5,
            'ano_referencia': 2026,
            'arquivo': SimpleUploadedFile("v1.pdf", b"%PDF-1.4 v1", content_type="application/pdf"),
            'observacao': 'Versão 1'
        })

        # Segundo envio — este deve ser o exibido na exportação
        self.client.post(url_upload, {
            'agente': self.agente.id,
            'mes_referencia': 5,
            'ano_referencia': 2026,
            'arquivo': SimpleUploadedFile("v2.pdf", b"%PDF-1.4 v2", content_type="application/pdf"),
            'observacao': 'Versão 2'
        })

        self.assertEqual(PrestacaoContas.objects.count(), 2)

        self.client.login(username="admin", password="password123")
        url = reverse('exportar_prestacao_csv')
        response = self.client.get(url, {'mes': 5, 'ano': 2026, 'formato': 'csv'})
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8-sig')
        lines = [l for l in content.split('\r\n') if l]

        # Contar quantas linhas de dados pertencem ao contrato 10/2026 (excluindo o cabeçalho)
        linhas_contrato = [l for l in lines[1:] if l.startswith('10/2026')]
        # Deve haver apenas 1 linha — o envio mais recente
        self.assertEqual(len(linhas_contrato), 1)

        # Limpeza
        for p in PrestacaoContas.objects.all():
            if p.arquivo and os.path.isfile(p.arquivo.path):
                os.remove(p.arquivo.path)

    def test_detalhe_publico_exibe_uma_linha_por_periodo_com_multiplos_envios(self):
        """Página pública de detalhes deve exibir apenas 1 linha por período mesmo com múltiplos envios."""
        url_upload = reverse('upload_prestacao', kwargs={'contrato_id': self.contrato.id})
        url_detalhe = reverse('detalhe_contrato', kwargs={'contrato_id': self.contrato.id})

        # Dois envios para o mesmo mês/ano
        for i in range(1, 3):
            self.client.post(url_upload, {
                'agente': self.agente.id,
                'mes_referencia': 5,
                'ano_referencia': 2026,
                'arquivo': SimpleUploadedFile(f"v{i}.pdf", b"%PDF-1.4", content_type="application/pdf"),
                'observacao': f'Versão {i}'
            })

        self.assertEqual(PrestacaoContas.objects.count(), 2)

        response = self.client.get(url_detalhe)
        self.assertEqual(response.status_code, 200)

        # O contexto 'prestacoes_recentes' deve retornar apenas 1 entrada para o período 05/2026
        prestacoes_recentes = response.context['prestacoes_recentes']
        periodos = [(p.mes_referencia, p.ano_referencia) for p in prestacoes_recentes]
        # Não pode haver entradas duplicadas no mesmo período
        self.assertEqual(len(periodos), len(set(periodos)))

        # Limpeza
        for p in PrestacaoContas.objects.all():
            if p.arquivo and os.path.isfile(p.arquivo.path):
                os.remove(p.arquivo.path)

    def test_exportar_historico_requer_login(self):
        """A exportação do histórico completo deve redirecionar usuários não autenticados para o login."""
        url = reverse('exportar_historico_prestacao_csv')
        response = self.client.get(url, {'formato': 'csv'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_alterar_status_workflow(self):
        """Testa as transições de status da prestação de contas e permissões de acesso"""
        # Criar prestação de contas
        pdf_file = SimpleUploadedFile("arq_wf.pdf", b"pdf_data", content_type="application/pdf")
        prestacao = PrestacaoContas.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=5,
            ano_referencia=2026,
            arquivo=pdf_file
        )
        self.assertEqual(prestacao.status, 'entregue')

        # Criar usuários de teste com diferentes permissões
        from django.contrib.auth.models import Group
        
        # 1. Usuário normal (sem privilégios)
        user_normal = User.objects.create_user(username="normal", password="password123")
        
        # 2. Auditor (grupo Auditores)
        grupo_auditores, _ = Group.objects.get_or_create(name='Auditores')
        user_auditor = User.objects.create_user(username="auditor", password="password123")
        user_auditor.groups.add(grupo_auditores)
        
        # 3. Administrador (Superuser ou grupo Administradores)
        user_admin = User.objects.create_superuser(username="superadmin", email="admin@test.com", password="password123")

        # Tentar alterar status sem login
        url_status_ok = reverse('alterar_status_prestacao', kwargs={'pk': prestacao.id, 'novo_status': 'ok'})
        response = self.client.get(url_status_ok)
        self.assertEqual(response.status_code, 302) # Redireciona para login

        # Tentar alterar status como usuário normal (deve ser rejeitado com redirect para dashboard_prestacao)
        self.client.login(username="normal", password="password123")
        response = self.client.get(url_status_ok)
        self.assertEqual(response.status_code, 302)
        self.assertTrue("portal/prestacao" in response.url)
        prestacao.refresh_from_db()
        self.assertEqual(prestacao.status, 'entregue') # Não alterado

        # Alterar status como Auditor (deve funcionar)
        self.client.login(username="auditor", password="password123")
        response = self.client.get(url_status_ok)
        self.assertEqual(response.status_code, 302)
        self.assertTrue("portal/prestacao" in response.url)
        prestacao.refresh_from_db()
        self.assertEqual(prestacao.status, 'ok') # Alterado para OK

        # Verifica se o novo status reflete na matriz renderizada no dashboard
        response_dash = self.client.get(reverse('dashboard_prestacao'))
        self.assertEqual(response_dash.status_code, 200)
        self.assertContains(response_dash, "Conformidade")

        # Alterar status para 'correcao' como Administrador (deve funcionar)
        # Agora requer POST com justificativa obrigatória via AJAX
        import json
        self.client.login(username="superadmin", password="password123")
        url_status_correcao = reverse('alterar_status_prestacao', kwargs={'pk': prestacao.id, 'novo_status': 'correcao'})
        response = self.client.post(
            url_status_correcao,
            data=json.dumps({'justificativa': 'Justificativa do teste de workflow'}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        prestacao.refresh_from_db()
        self.assertEqual(prestacao.status, 'correcao') # Alterado para correção

        # Verifica se o status de correção reflete na matriz renderizada no dashboard
        response_dash = self.client.get(reverse('dashboard_prestacao'))
        self.assertEqual(response_dash.status_code, 200)
        self.assertContains(response_dash, "Corrigir")

        # Tentar passar status inválido
        url_status_invalido = reverse('alterar_status_prestacao', kwargs={'pk': prestacao.id, 'novo_status': 'invalido'})
        response = self.client.get(url_status_invalido)
        self.assertEqual(response.status_code, 302)
        prestacao.refresh_from_db()
        self.assertEqual(prestacao.status, 'correcao') # Permanece o mesmo

        # Limpar arquivo gerado no teste
        if prestacao.arquivo and os.path.isfile(prestacao.arquivo.path):
            os.remove(prestacao.arquivo.path)

    def test_reordenar_gestores_prio_permissoes(self):
        """Apenas auditores/admins podem chamar o endpoint de reordenação"""
        import json
        from django.contrib.auth.models import Group

        url = reverse('reordenar_gestores_prio')
        payload = json.dumps({'agente_ids': [self.agente.id]})

        # Sem login → 302 para login
        response = self.client.post(
            url, data=payload, content_type='application/json'
        )
        self.assertEqual(response.status_code, 302)

        # Usuário sem permissão → 403
        user_normal = User.objects.create_user(username='normal_reord', password='password123')
        self.client.login(username='normal_reord', password='password123')
        response = self.client.post(
            url, data=payload, content_type='application/json'
        )
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertEqual(data['status'], 'error')

        # Auditor → 200 com sucesso
        grupo_auditores, _ = Group.objects.get_or_create(name='Auditores')
        user_auditor = User.objects.create_user(username='auditor_reord', password='password123')
        user_auditor.groups.add(grupo_auditores)
        self.client.login(username='auditor_reord', password='password123')
        response = self.client.post(
            url, data=payload, content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')

    def test_reordenar_gestores_prio_persiste_ordem(self):
        """O endpoint deve atualizar o campo ordem_manual de cada agente na ordem correta"""
        import json
        from django.contrib.auth.models import Group

        # Criar segundo agente do mesmo posto
        agente2 = Agente.objects.create(
            nome_completo="Maria Costa",
            nome_de_guerra="Costa",
            posto=self.posto,
            saram="9999999"
        )

        # Configurar auditor
        grupo_auditores, _ = Group.objects.get_or_create(name='Auditores')
        user_auditor = User.objects.create_user(username='auditor_persist', password='password123')
        user_auditor.groups.add(grupo_auditores)
        self.client.login(username='auditor_persist', password='password123')

        url = reverse('reordenar_gestores_prio')
        # Enviar agente2 primeiro, self.agente depois (inverso da criação)
        payload = json.dumps({'agente_ids': [agente2.id, self.agente.id]})
        response = self.client.post(url, data=payload, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')

        # Verificar no banco
        agente2.refresh_from_db()
        self.agente.refresh_from_db()
        self.assertEqual(agente2.ordem_manual, 0.0)
        self.assertEqual(self.agente.ordem_manual, 1.0)

    def test_reordenar_gestores_prio_payload_invalido(self):
        """Payload inválido deve retornar 400"""
        import json
        from django.contrib.auth.models import Group

        grupo_auditores, _ = Group.objects.get_or_create(name='Auditores')
        user_auditor = User.objects.create_user(username='auditor_inv', password='password123')
        user_auditor.groups.add(grupo_auditores)
        self.client.login(username='auditor_inv', password='password123')

        url = reverse('reordenar_gestores_prio')
        # Enviar JSON malformado
        response = self.client.post(url, data='NAO_EH_JSON', content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['status'], 'error')

    def test_detalhe_publico_status_prestacao(self):
        """A página pública de detalhamento deve exibir o ícone correto para cada status"""
        import os
        from django.core.files.uploadedfile import SimpleUploadedFile

        url = reverse('detalhe_contrato', kwargs={'contrato_id': self.contrato.id})

        pdf_file = SimpleUploadedFile("arq_detalhe.pdf", b"pdf_data", content_type="application/pdf")
        prestacao = PrestacaoContas.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=5,
            ano_referencia=2026,
            arquivo=pdf_file,
            status='entregue'
        )

        # Status 'entregue' → ícone bi-file-earmark-arrow-up
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'bi-file-earmark-arrow-up')

        # Status 'correcao' → ícone bi-exclamation-triangle-fill
        prestacao.status = 'correcao'
        prestacao.save()
        response = self.client.get(url)
        self.assertContains(response, 'bi-exclamation-triangle-fill')

        # Status 'ok' → ícone bi-check-circle-fill
        prestacao.status = 'ok'
        prestacao.save()
        response = self.client.get(url)
        self.assertContains(response, 'bi-check-circle-fill')

        # Limpar arquivo gerado no teste
        if prestacao.arquivo and os.path.isfile(prestacao.arquivo.path):
            os.remove(prestacao.arquivo.path)

    def test_gestores_prio_ordem_manual(self):
        """No dashboard, dois agentes do mesmo posto devem aparecer na ordem definida por ordem_manual"""
        from django.contrib.auth.models import Group

        # Criar segundo agente do mesmo posto com ordem_manual diferente
        agente2 = Agente.objects.create(
            nome_completo="Pedro Ramos",
            nome_de_guerra="Ramos",
            posto=self.posto,
            saram="8888888",
            ordem_manual=0.0  # Deve vir ANTES de self.agente
        )
        self.agente.ordem_manual = 1.0
        self.agente.save()

        # Criar contratos e prestações marcadas como prioritárias para ambos
        contrato2 = Contrato.objects.create(
            numero="20/2026",
            objeto="Serviços de Teste 2",
            empresa=self.empresa,
            vigencia_inicio=date(2026, 1, 1),
            vigencia_fim=date(2026, 12, 31),
            valor_total=2000.00
        )

        hoje = date.today()
        pdf1 = SimpleUploadedFile("arq_prio1.pdf", b"pdf", content_type="application/pdf")
        pdf2 = SimpleUploadedFile("arq_prio2.pdf", b"pdf", content_type="application/pdf")

        prest1 = PrestacaoContas.objects.create(
            contrato=self.contrato, agente=self.agente,
            mes_referencia=hoje.month, ano_referencia=hoje.year,
            arquivo=pdf1, compor_apresentacao=True, status='ok'
        )
        prest2 = PrestacaoContas.objects.create(
            contrato=contrato2, agente=agente2,
            mes_referencia=hoje.month, ano_referencia=hoje.year,
            arquivo=pdf2, compor_apresentacao=True, status='ok'
        )

        # Autenticar como auditor para acessar o dashboard
        grupo_auditores, _ = Group.objects.get_or_create(name='Auditores')
        user_auditor = User.objects.create_user(username='auditor_ordem', password='password123')
        user_auditor.groups.add(grupo_auditores)
        self.client.login(username='auditor_ordem', password='password123')

        response = self.client.get(reverse('dashboard_prestacao'))
        self.assertEqual(response.status_code, 200)

        gestores_prio = response.context['gestores_prio']
        nomes = [g['gestor'] for g in gestores_prio]

        # agente2 tem ordem_manual=0.0, deve vir antes de self.agente (ordem_manual=1.0)
        self.assertIn('SGT Ramos', nomes)
        self.assertIn('SGT Silva', nomes)
        self.assertLess(nomes.index('SGT Ramos'), nomes.index('SGT Silva'))

        # Limpar arquivos gerados no teste
        for prest in [prest1, prest2]:
            if prest.arquivo and os.path.isfile(prest.arquivo.path):
                os.remove(prest.arquivo.path)

    def test_exportar_historico_completo(self):
        """Testa exportação do histórico completo de prestações de contas"""
        pdf_file = SimpleUploadedFile("arq_historico.pdf", b"pdf_data_hist", content_type="application/pdf")
        prest1 = PrestacaoContas.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=5,
            ano_referencia=2026,
            arquivo=pdf_file,
            status='entregue'
        )
        
        self.client.login(username="admin", password="password123")
        url = reverse('exportar_historico_prestacao_csv')
        
        response = self.client.get(url, {'formato': 'csv'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        
        content = response.content.decode('utf-8-sig')
        lines = content.split('\r\n')
        self.assertIn('Contrato', lines[0])
        self.assertIn('Mês de Referência', lines[0])
        self.assertIn('Ano de Referência', lines[0])
        
        # Limpar arquivo gerado no teste
        if prest1.arquivo and os.path.isfile(prest1.arquivo.path):
            os.remove(prest1.arquivo.path)


