from django.test import TestCase, Client
from django.urls import reverse

class ErrorHandlingTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_pagina_inexistente_retorna_404_personalizado(self):
        """Acesso a um caminho inexistente deve retornar HTTP 404 e usar o template 404.html"""
        response = self.client.get('/caminho-que-nao-existe-12345/')
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, '404.html')
        self.assertContains(response, 'Página não encontrada', status_code=404)
        self.assertContains(response, '404', status_code=404)
