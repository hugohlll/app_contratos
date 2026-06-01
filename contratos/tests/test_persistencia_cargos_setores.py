"""
Testes de persistência para Setor e CargoRegimental.

Foco: garantir que os dados são efetivamente salvos no banco de dados
em cada camada (ORM direto, formulário, e view HTTP POST).
"""
import json
from datetime import date

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group
from django.db import IntegrityError

from contratos.models import Setor, CargoRegimental, Agente, PostoGraduacao
from contratos.forms import SetorForm, CargoRegimentalForm


# ======================================================================
# HELPERS
# ======================================================================

class BaseTestCase(TestCase):
    """Fixtures comuns a todos os testes de persistência."""

    def setUp(self):
        self.client = Client()

        # Posto / Agente
        self.posto = PostoGraduacao.objects.create(
            sigla="CAP", descricao="Capitão", senioridade=3
        )
        self.agente = Agente.objects.create(
            nome_completo="Carlos Eduardo Rocha",
            nome_de_guerra="Rocha",
            posto=self.posto,
            saram="9999901",
        )
        self.agente2 = Agente.objects.create(
            nome_completo="Pedro Alvares Cabral",
            nome_de_guerra="Cabral",
            posto=self.posto,
            saram="9999902",
        )

        # Grupos
        self.grupo_auditores, _ = Group.objects.get_or_create(name="Auditores")

        # Usuários
        self.admin = User.objects.create_superuser(
            username="adm_persist", password="Senha@123"
        )
        self.auditor = User.objects.create_user(
            username="aud_persist", password="Senha@123"
        )
        self.auditor.groups.add(self.grupo_auditores)

        self.user_normal = User.objects.create_user(
            username="normal_persist", password="Senha@123"
        )


# ======================================================================
# 1) PERSISTÊNCIA DIRETA VIA ORM
# ======================================================================

class SetorOrmPersistenciaTest(BaseTestCase):
    """Setor: criação, leitura, atualização e exclusão via ORM."""

    def test_criar_setor_persiste_no_banco(self):
        """Setor.objects.create() deve inserir um registro no BD."""
        setor = Setor.objects.create(nome="Seção de Informática", sigla="SI", ordem=1)
        self.assertEqual(Setor.objects.filter(pk=setor.pk).count(), 1)

        reloaded = Setor.objects.get(pk=setor.pk)
        self.assertEqual(reloaded.nome, "Seção de Informática")
        self.assertEqual(reloaded.sigla, "SI")
        self.assertEqual(reloaded.ordem, 1)

    def test_criar_setor_sem_sigla(self):
        """Sigla é opcional — o setor deve persistir sem ela."""
        setor = Setor.objects.create(nome="Almoxarifado")
        self.assertIsNone(setor.sigla)
        self.assertEqual(Setor.objects.filter(pk=setor.pk).count(), 1)

    def test_atualizar_setor_persiste(self):
        """Atualização de campos deve refletir no BD."""
        setor = Setor.objects.create(nome="Provisório", sigla="PROV")
        setor.nome = "Definitivo"
        setor.sigla = "DEF"
        setor.save()

        reloaded = Setor.objects.get(pk=setor.pk)
        self.assertEqual(reloaded.nome, "Definitivo")
        self.assertEqual(reloaded.sigla, "DEF")

    def test_excluir_setor_remove_do_banco(self):
        """Setor excluído não deve mais existir no BD."""
        setor = Setor.objects.create(nome="Temporario")
        pk = setor.pk
        setor.delete()
        self.assertFalse(Setor.objects.filter(pk=pk).exists())

    def test_setor_nome_unico(self):
        """Dois setores com mesmo nome devem provocar IntegrityError."""
        Setor.objects.create(nome="Duplicado")
        with self.assertRaises(IntegrityError):
            Setor.objects.create(nome="Duplicado")

    def test_str_setor_com_sigla(self):
        setor = Setor.objects.create(nome="Seção A", sigla="SA")
        self.assertEqual(str(setor), "SA - Seção A")

    def test_str_setor_sem_sigla(self):
        setor = Setor.objects.create(nome="Seção B")
        self.assertEqual(str(setor), "Seção B")


class CargoRegimentalOrmPersistenciaTest(BaseTestCase):
    """CargoRegimental: CRUD via ORM."""

    def test_criar_cargo_persiste_no_banco(self):
        """CargoRegimental.objects.create() deve inserir um registro."""
        setor = Setor.objects.create(nome="Logística", sigla="LOG")
        cargo = CargoRegimental.objects.create(
            setor=setor,
            agente=self.agente,
            cargo="Chefe de Logística",
            boletim_numero="BI 45/2026",
            boletim_data=date(2026, 3, 15),
            ativo=True,
        )
        self.assertEqual(CargoRegimental.objects.filter(pk=cargo.pk).count(), 1)

        reloaded = CargoRegimental.objects.get(pk=cargo.pk)
        self.assertEqual(reloaded.cargo, "Chefe de Logística")
        self.assertEqual(reloaded.setor, setor)
        self.assertEqual(reloaded.agente, self.agente)
        self.assertTrue(reloaded.ativo)
        self.assertEqual(reloaded.boletim_numero, "BI 45/2026")
        self.assertEqual(reloaded.boletim_data, date(2026, 3, 15))

    def test_criar_cargo_campos_opcionais_vazios(self):
        """Boletim e observação podem ser nulos — deve persistir."""
        setor = Setor.objects.create(nome="Financeiro")
        cargo = CargoRegimental.objects.create(
            setor=setor, agente=self.agente, cargo="Tesoureiro"
        )
        reloaded = CargoRegimental.objects.get(pk=cargo.pk)
        self.assertIsNone(reloaded.boletim_numero)
        self.assertIsNone(reloaded.boletim_data)
        self.assertIsNone(reloaded.observacao)
        self.assertTrue(reloaded.ativo)  # default

    def test_atualizar_cargo_persiste(self):
        """Atualização de cargo deve refletir no BD."""
        setor = Setor.objects.create(nome="Operações")
        cargo = CargoRegimental.objects.create(
            setor=setor, agente=self.agente, cargo="Adjunto"
        )
        cargo.cargo = "Chefe de Operações"
        cargo.ativo = False
        cargo.save()

        reloaded = CargoRegimental.objects.get(pk=cargo.pk)
        self.assertEqual(reloaded.cargo, "Chefe de Operações")
        self.assertFalse(reloaded.ativo)

    def test_excluir_cargo_remove_do_banco(self):
        """Cargo excluído não deve mais existir."""
        setor = Setor.objects.create(nome="Temp")
        cargo = CargoRegimental.objects.create(
            setor=setor, agente=self.agente, cargo="Temp"
        )
        pk = cargo.pk
        cargo.delete()
        self.assertFalse(CargoRegimental.objects.filter(pk=pk).exists())

    def test_cascade_setor_exclui_cargos(self):
        """Exclusão do setor deve excluir cargos via CASCADE."""
        setor = Setor.objects.create(nome="Setor Cascade")
        cargo = CargoRegimental.objects.create(
            setor=setor, agente=self.agente, cargo="Cargo Cascade"
        )
        cargo_pk = cargo.pk
        setor.delete()
        self.assertFalse(CargoRegimental.objects.filter(pk=cargo_pk).exists())

    def test_protect_agente_impede_exclusao(self):
        """Agente com cargo regimental não deve ser excluído (PROTECT)."""
        setor = Setor.objects.create(nome="Protect Test")
        CargoRegimental.objects.create(
            setor=setor, agente=self.agente, cargo="Protegido"
        )
        from django.db.models import ProtectedError
        with self.assertRaises(ProtectedError):
            self.agente.delete()

    def test_str_cargo_regimental(self):
        setor = Setor.objects.create(nome="TI", sigla="TI")
        cargo = CargoRegimental.objects.create(
            setor=setor, agente=self.agente, cargo="Chefe de TI"
        )
        expected = f"Chefe de TI - {self.agente} ({setor})"
        self.assertEqual(str(cargo), expected)


# ======================================================================
# 2) PERSISTÊNCIA VIA FORMULÁRIOS (Forms)
# ======================================================================

class SetorFormPersistenciaTest(BaseTestCase):
    """SetorForm: validação e save()."""

    def test_form_valido_salva_setor(self):
        """Submissão válida do SetorForm deve criar o registro."""
        form = SetorForm(data={"nome": "Seção de Pessoal", "sigla": "SP"})
        self.assertTrue(form.is_valid(), f"Erros: {form.errors}")
        setor = form.save()
        self.assertEqual(Setor.objects.filter(pk=setor.pk).count(), 1)
        self.assertEqual(setor.nome, "Seção de Pessoal")

    def test_form_sem_nome_invalido(self):
        """Nome é obrigatório — form deve ser inválido."""
        form = SetorForm(data={"nome": "", "sigla": "X"})
        self.assertFalse(form.is_valid())
        self.assertIn("nome", form.errors)

    def test_form_nome_duplicado_invalido(self):
        """Nomes duplicados devem ser rejeitados pelo form."""
        Setor.objects.create(nome="Duplicado")
        form = SetorForm(data={"nome": "Duplicado", "sigla": "DUP"})
        self.assertFalse(form.is_valid())
        self.assertIn("nome", form.errors)

    def test_form_sigla_opcional(self):
        """Form deve aceitar sigla em branco."""
        form = SetorForm(data={"nome": "Sem Sigla", "sigla": ""})
        self.assertTrue(form.is_valid(), f"Erros: {form.errors}")
        setor = form.save()
        self.assertIsNotNone(setor.pk)


class CargoRegimentalFormPersistenciaTest(BaseTestCase):
    """CargoRegimentalForm: validação e save()."""

    def setUp(self):
        super().setUp()
        self.setor = Setor.objects.create(nome="Setor Form Test", sigla="SFT")

    def test_form_valido_salva_cargo(self):
        """Submissão válida do CargoRegimentalForm deve persistir."""
        data = {
            "setor": self.setor.id,
            "agente": self.agente.id,
            "cargo": "Chefe da Seção",
            "boletim_numero": "BI 10/2026",
            "boletim_data": "2026-01-15",
            "ativo": True,
            "observacao": "",
        }
        form = CargoRegimentalForm(data=data)
        self.assertTrue(form.is_valid(), f"Erros: {form.errors}")
        cargo = form.save()
        self.assertEqual(CargoRegimental.objects.filter(pk=cargo.pk).count(), 1)

        reloaded = CargoRegimental.objects.get(pk=cargo.pk)
        self.assertEqual(reloaded.cargo, "Chefe da Seção")
        self.assertEqual(reloaded.setor, self.setor)
        self.assertEqual(reloaded.agente, self.agente)

    def test_form_campos_obrigatorios(self):
        """Setor, agente e cargo são obrigatórios."""
        form = CargoRegimentalForm(data={})
        self.assertFalse(form.is_valid())
        self.assertIn("setor", form.errors)
        self.assertIn("agente", form.errors)
        self.assertIn("cargo", form.errors)

    def test_form_sem_boletim_valido(self):
        """Boletim é opcional — form deve aceitar sem ele."""
        data = {
            "setor": self.setor.id,
            "agente": self.agente.id,
            "cargo": "Adjunto",
            "ativo": True,
        }
        form = CargoRegimentalForm(data=data)
        self.assertTrue(form.is_valid(), f"Erros: {form.errors}")
        cargo = form.save()
        self.assertIsNotNone(cargo.pk)

    def test_form_edicao_persiste_alteracao(self):
        """Edição via form (com instance) deve atualizar o registro."""
        cargo = CargoRegimental.objects.create(
            setor=self.setor, agente=self.agente, cargo="Original"
        )
        data = {
            "setor": self.setor.id,
            "agente": self.agente2.id,
            "cargo": "Alterado via Form",
            "ativo": False,
        }
        form = CargoRegimentalForm(data=data, instance=cargo)
        self.assertTrue(form.is_valid(), f"Erros: {form.errors}")
        form.save()

        reloaded = CargoRegimental.objects.get(pk=cargo.pk)
        self.assertEqual(reloaded.cargo, "Alterado via Form")
        self.assertEqual(reloaded.agente, self.agente2)
        self.assertFalse(reloaded.ativo)


# ======================================================================
# 3) PERSISTÊNCIA VIA VIEWS (HTTP POST end-to-end)
# ======================================================================

class SetorViewPersistenciaTest(BaseTestCase):
    """Setor: criação e exclusão via views HTTP."""

    def test_post_novo_setor_persiste(self):
        """POST em novo_setor com dados válidos deve salvar no BD."""
        self.client.login(username="adm_persist", password="Senha@123")
        url = reverse("novo_setor")
        data = {"nome": "Setor Criado via View", "sigla": "SCV"}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 302)  # redirect
        self.assertTrue(
            Setor.objects.filter(nome="Setor Criado via View").exists(),
            "Setor NÃO foi persistido no banco após POST na view novo_setor.",
        )

    def test_post_novo_setor_auditor_persiste(self):
        """Auditor também pode criar setor via view."""
        self.client.login(username="aud_persist", password="Senha@123")
        url = reverse("novo_setor")
        data = {"nome": "Setor Auditor", "sigla": "SA"}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Setor.objects.filter(nome="Setor Auditor").exists(),
            "Setor NÃO foi persistido quando criado por auditor.",
        )

    def test_post_novo_setor_usuario_normal_nao_persiste(self):
        """Usuário normal NÃO deve conseguir criar setor."""
        self.client.login(username="normal_persist", password="Senha@123")
        url = reverse("novo_setor")
        data = {"nome": "Setor Proibido", "sigla": "SP"}
        self.client.post(url, data)

        self.assertFalse(
            Setor.objects.filter(nome="Setor Proibido").exists(),
            "Setor foi persistido por usuário sem permissão!",
        )

    def test_post_excluir_setor_remove_do_banco(self):
        """POST em excluir_setor deve remover efetivamente do BD."""
        setor = Setor.objects.create(nome="Para Excluir")
        self.client.login(username="adm_persist", password="Senha@123")
        url = reverse("excluir_setor", kwargs={"pk": setor.pk})
        self.client.post(url)

        self.assertFalse(
            Setor.objects.filter(pk=setor.pk).exists(),
            "Setor NÃO foi removido do banco após POST na view excluir_setor.",
        )

    def test_post_excluir_setor_com_cargos_nao_remove(self):
        """Setor com cargos vinculados NÃO pode ser excluído via view."""
        setor = Setor.objects.create(nome="Setor com Cargos")
        CargoRegimental.objects.create(
            setor=setor, agente=self.agente, cargo="Chefe"
        )
        self.client.login(username="adm_persist", password="Senha@123")
        url = reverse("excluir_setor", kwargs={"pk": setor.pk})
        self.client.post(url)

        self.assertTrue(
            Setor.objects.filter(pk=setor.pk).exists(),
            "Setor com cargos vinculados foi excluído indevidamente!",
        )


class CargoRegimentalViewPersistenciaTest(BaseTestCase):
    """CargoRegimental: criação, edição e exclusão via views HTTP."""

    def setUp(self):
        super().setUp()
        self.setor = Setor.objects.create(nome="Setor View Test", sigla="SVT")

    def test_post_novo_cargo_persiste(self):
        """POST em cargos_regimentais com dados válidos deve salvar."""
        self.client.login(username="adm_persist", password="Senha@123")
        url = reverse("cargos_regimentais")
        data = {
            "setor": self.setor.id,
            "agente": self.agente.id,
            "cargo": "Cargo via View POST",
            "ativo": True,
        }
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            CargoRegimental.objects.filter(cargo="Cargo via View POST").exists(),
            "CargoRegimental NÃO foi persistido no banco após POST na view.",
        )

    def test_post_novo_cargo_auditor_persiste(self):
        """Auditor deve conseguir criar cargo via POST."""
        self.client.login(username="aud_persist", password="Senha@123")
        url = reverse("cargos_regimentais")
        data = {
            "setor": self.setor.id,
            "agente": self.agente.id,
            "cargo": "Cargo Auditor POST",
            "ativo": True,
        }
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            CargoRegimental.objects.filter(cargo="Cargo Auditor POST").exists(),
            "CargoRegimental NÃO foi persistido quando criado por auditor.",
        )

    def test_post_novo_cargo_usuario_normal_nao_persiste(self):
        """Usuário normal NÃO deve conseguir criar cargo."""
        self.client.login(username="normal_persist", password="Senha@123")
        url = reverse("cargos_regimentais")
        data = {
            "setor": self.setor.id,
            "agente": self.agente.id,
            "cargo": "Cargo Proibido",
            "ativo": True,
        }
        self.client.post(url, data)

        self.assertFalse(
            CargoRegimental.objects.filter(cargo="Cargo Proibido").exists(),
            "CargoRegimental foi persistido por usuário sem permissão!",
        )

    def test_post_editar_cargo_persiste(self):
        """POST em editar_cargo_regimental deve atualizar no BD."""
        cargo = CargoRegimental.objects.create(
            setor=self.setor, agente=self.agente, cargo="Antes da Edição"
        )
        self.client.login(username="adm_persist", password="Senha@123")
        url = reverse("editar_cargo_regimental", kwargs={"pk": cargo.pk})
        data = {
            "setor": self.setor.id,
            "agente": self.agente2.id,
            "cargo": "Depois da Edição",
            "ativo": False,
        }
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 302)
        cargo.refresh_from_db()
        self.assertEqual(cargo.cargo, "Depois da Edição")
        self.assertEqual(cargo.agente, self.agente2)
        self.assertFalse(cargo.ativo)

    def test_post_excluir_cargo_remove_do_banco(self):
        """POST em excluir_cargo_regimental deve remover do BD."""
        cargo = CargoRegimental.objects.create(
            setor=self.setor, agente=self.agente, cargo="Para Excluir"
        )
        self.client.login(username="adm_persist", password="Senha@123")
        url = reverse("excluir_cargo_regimental", kwargs={"pk": cargo.pk})
        self.client.post(url)

        self.assertFalse(
            CargoRegimental.objects.filter(pk=cargo.pk).exists(),
            "CargoRegimental NÃO foi removido do banco após POST.",
        )

    def test_post_cargo_com_todos_campos_opcionais(self):
        """Cargo com boletim e observação preenchidos deve persistir tudo."""
        self.client.login(username="adm_persist", password="Senha@123")
        url = reverse("cargos_regimentais")
        data = {
            "setor": self.setor.id,
            "agente": self.agente.id,
            "cargo": "Cargo Completo",
            "boletim_numero": "BI 99/2026",
            "boletim_data": "2026-05-01",
            "ativo": True,
            "observacao": "Teste observação",
        }
        self.client.post(url, data)

        cargo = CargoRegimental.objects.get(cargo="Cargo Completo")
        self.assertEqual(cargo.boletim_numero, "BI 99/2026")
        self.assertEqual(cargo.boletim_data, date(2026, 5, 1))
        self.assertEqual(cargo.observacao, "Teste observação")


# ======================================================================
# 4) PERSISTÊNCIA DA REORDENAÇÃO DE SETORES
# ======================================================================

class ReordenacaoSetorPersistenciaTest(BaseTestCase):
    """Reordenação de setores via API JSON deve persistir no BD."""

    def test_reordenar_setores_persiste_ordem(self):
        """A nova ordem dos setores deve estar salva no BD."""
        s1 = Setor.objects.create(nome="Setor A", ordem=0)
        s2 = Setor.objects.create(nome="Setor B", ordem=1)
        s3 = Setor.objects.create(nome="Setor C", ordem=2)

        self.client.login(username="adm_persist", password="Senha@123")
        url = reverse("reordenar_setores")
        payload = {"setor_ids": [s3.id, s1.id, s2.id]}

        response = self.client.post(
            url, json.dumps(payload), content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)

        s1.refresh_from_db()
        s2.refresh_from_db()
        s3.refresh_from_db()

        self.assertEqual(s3.ordem, 0)
        self.assertEqual(s1.ordem, 1)
        self.assertEqual(s2.ordem, 2)

    def test_reordenar_setores_usuario_normal_nao_altera(self):
        """Usuário normal NÃO pode reordenar setores."""
        s1 = Setor.objects.create(nome="Setor X", ordem=0)
        s2 = Setor.objects.create(nome="Setor Y", ordem=1)

        self.client.login(username="normal_persist", password="Senha@123")
        url = reverse("reordenar_setores")
        payload = {"setor_ids": [s2.id, s1.id]}

        response = self.client.post(
            url, json.dumps(payload), content_type="application/json"
        )
        self.assertEqual(response.status_code, 403)

        # Ordem original mantida
        s1.refresh_from_db()
        s2.refresh_from_db()
        self.assertEqual(s1.ordem, 0)
        self.assertEqual(s2.ordem, 1)


# ======================================================================
# 5) CONTAGEM DE REGISTROS PÓS-OPERAÇÕES EM LOTE
# ======================================================================

class ContagemRegistrosTest(BaseTestCase):
    """Verifica que a contagem final no banco reflete todas as inserções."""

    def test_criar_multiplos_setores(self):
        """Múltiplos setores devem ser criados e contados corretamente."""
        nomes = [f"Setor Lote {i}" for i in range(5)]
        for nome in nomes:
            Setor.objects.create(nome=nome)
        self.assertEqual(Setor.objects.filter(nome__startswith="Setor Lote").count(), 5)

    def test_criar_multiplos_cargos_para_mesmo_setor(self):
        """Um setor pode ter múltiplos cargos e todos devem persistir."""
        setor = Setor.objects.create(nome="Multi Cargos")
        for i in range(3):
            agente = Agente.objects.create(
                nome_completo=f"Agente {i}",
                nome_de_guerra=f"AG{i}",
                posto=self.posto,
                saram=f"888880{i}",
            )
            CargoRegimental.objects.create(
                setor=setor, agente=agente, cargo=f"Cargo {i}"
            )
        self.assertEqual(setor.cargos.count(), 3)

    def test_contagem_zero_em_banco_limpo(self):
        """Em banco limpo (sem setUp de fixtures), contagem deve ser 0."""
        # Cargos criados no setUp não existem aqui — base limpa por teste.
        # Não criamos nada, então os modelos devem estar vazios.
        self.assertEqual(Setor.objects.count(), 0)
        self.assertEqual(CargoRegimental.objects.count(), 0)
