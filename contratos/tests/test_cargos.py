import json
from datetime import date
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group

from contratos.models import Setor, CargoRegimental, Agente, PostoGraduacao

class CargosRegimentaisTests(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Criação de postos e agentes
        self.posto = PostoGraduacao.objects.create(sigla="SGT", descricao="Sargento", senioridade=5)
        self.agente = Agente.objects.create(
            nome_completo="Joao Silva", 
            nome_de_guerra="Silva", 
            posto=self.posto, 
            saram="1234567"
        )
        
        # Criação de setor
        self.setor = Setor.objects.create(nome="Setor de Testes", sigla="ST", ordem=1)
        
        # Criação de cargo regimental
        self.cargo = CargoRegimental.objects.create(
            setor=self.setor,
            agente=self.agente,
            cargo="Chefe da Seção",
            boletim_numero="BO 123",
            boletim_data=date(2026, 1, 1),
            ativo=True
        )

        # Usuários e Grupos
        self.grupo_auditores, _ = Group.objects.get_or_create(name='Auditores')
        
        self.user_normal = User.objects.create_user(username="normal", password="password123")
        
        self.user_auditor = User.objects.create_user(username="auditor", password="password123")
        self.user_auditor.groups.add(self.grupo_auditores)
        
        self.user_admin = User.objects.create_superuser(username="admin", password="password123")

    def test_cargos_regimentais_view_requer_login(self):
        """A visualização principal requer login"""
        url = reverse('cargos_regimentais')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_cargos_regimentais_acesso_usuarios(self):
        """Todos os usuários logados podem ver a página"""
        self.client.login(username="normal", password="password123")
        url = reverse('cargos_regimentais')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Setor de Testes")
        self.assertContains(response, "Chefe da Seção")

    def test_cadastrar_cargo_permissao(self):
        """Apenas auditores e admins podem cadastrar cargos"""
        url = reverse('cargos_regimentais')
        data = {
            'setor': self.setor.id,
            'agente': self.agente.id,
            'cargo': 'Novo Cargo',
            'ativo': True
        }

        # Usuário normal não deve conseguir cadastrar (post é ignorado/bloqueado)
        self.client.login(username="normal", password="password123")
        self.client.post(url, data)
        self.assertEqual(CargoRegimental.objects.filter(cargo='Novo Cargo').count(), 0)

        # Auditor deve conseguir
        self.client.login(username="auditor", password="password123")
        self.client.post(url, data)
        self.assertEqual(CargoRegimental.objects.filter(cargo='Novo Cargo').count(), 1)

    def test_excluir_cargo_regimental_permissao(self):
        """Apenas administradores podem excluir cargos regimentais"""
        url = reverse('excluir_cargo_regimental', kwargs={'pk': self.cargo.id})

        # Auditor tenta excluir e é negado
        self.client.login(username="auditor", password="password123")
        self.client.post(url)
        self.assertTrue(CargoRegimental.objects.filter(id=self.cargo.id).exists())

        # Admin exclui com sucesso
        self.client.login(username="admin", password="password123")
        self.client.post(url)
        self.assertFalse(CargoRegimental.objects.filter(id=self.cargo.id).exists())

    def test_excluir_setor_seguro(self):
        """Não é possível excluir um setor que possui cargos regimentais vinculados"""
        url = reverse('excluir_setor', kwargs={'pk': self.setor.id})

        self.client.login(username="admin", password="password123")
        # Tentativa de exclusão com cargo vinculado
        self.client.post(url)
        self.assertTrue(Setor.objects.filter(id=self.setor.id).exists()) # Ainda existe

        # Remove o cargo vinculado
        self.cargo.delete()

        # Agora a exclusão deve funcionar
        self.client.post(url)
        self.assertFalse(Setor.objects.filter(id=self.setor.id).exists()) # Foi excluído

    def test_editar_cargo_regimental(self):
        """Auditores e admins podem editar um cargo regimental"""
        url = reverse('editar_cargo_regimental', kwargs={'pk': self.cargo.id})
        data = {
            'setor': self.setor.id,
            'agente': self.agente.id,
            'cargo': 'Cargo Editado',
            'ativo': False
        }

        # Auditor edita com sucesso
        self.client.login(username="auditor", password="password123")
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        
        self.cargo.refresh_from_db()
        self.assertEqual(self.cargo.cargo, 'Cargo Editado')
        self.assertFalse(self.cargo.ativo)

    def test_novo_setor_permissao(self):
        """Apenas auditores e admins podem criar um novo setor"""
        url = reverse('novo_setor')
        data = {
            'nome': 'Setor Administrativo',
            'sigla': 'SA',
            'ordem': 2
        }

        # Usuário normal é negado
        self.client.login(username="normal", password="password123")
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Setor.objects.filter(nome='Setor Administrativo').exists())

        # Admin cria com sucesso
        self.client.login(username="admin", password="password123")
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Setor.objects.filter(nome='Setor Administrativo').exists())

    def test_excluir_setor_permissao(self):
        """Apenas administradores podem excluir setores (mesmo vazios)"""
        # Cria setor vazio
        setor_vazio = Setor.objects.create(nome="Setor Vazio")
        url = reverse('excluir_setor', kwargs={'pk': setor_vazio.id})
        
        # Auditor tenta excluir e falha
        self.client.login(username="auditor", password="password123")
        self.client.post(url)
        self.assertTrue(Setor.objects.filter(id=setor_vazio.id).exists())

        # Admin exclui com sucesso
        self.client.login(username="admin", password="password123")
        self.client.post(url)
        self.assertFalse(Setor.objects.filter(id=setor_vazio.id).exists())

    def test_reordenar_setores_permissao_e_persistencia(self):
        """Apenas administradores podem reordenar setores e a nova ordem é salva no BD"""
        url = reverse('reordenar_setores')
        setor2 = Setor.objects.create(nome="Setor 2", ordem=2)
        
        data = {
            'setor_ids': [setor2.id, self.setor.id]  # Invertendo a ordem
        }

        # Normal tenta e falha (nem view consegue bater sem auth)
        self.client.login(username="normal", password="password123")
        response = self.client.post(url, json.dumps(data), content_type="application/json")
        self.assertEqual(response.status_code, 403)

        # Admin altera a ordem com sucesso
        self.client.login(username="admin", password="password123")
        response = self.client.post(url, json.dumps(data), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        
        self.setor.refresh_from_db()
        setor2.refresh_from_db()
        
        self.assertEqual(setor2.ordem, 0)
        self.assertEqual(self.setor.ordem, 1)
