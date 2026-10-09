"""
Serviço de modularização e configuração de blocos do Livro do Fiscal (Livro de Ocorrências).

Permite habilitar, desabilitar ou adaptar blocos acessórios (como Preposto da Contratada
e Regime de Obras/Engenharia) de forma centralizada e independente, garantindo facilidade
de reinclusão no formulário no momento oportuno.
"""

from typing import Dict, Any


class ModulosLivroFiscalService:
    """
    Controlador de estado e renderização dos blocos modulares do Livro de Ocorrências.
    """
    # Por padrão, os blocos 2 (Preposto) e 3 (Obras/Engenharia) estão desativados no formulário
    BLOCO_PREPOSTO_HABILITADO: bool = False
    BLOCO_OBRAS_HABILITADO: bool = False

    @classmethod
    def is_preposto_habilitado(cls) -> bool:
        """Indica se a seção 'Preposto Aceito da Contratada' deve ser exibida no formulário."""
        return cls.BLOCO_PREPOSTO_HABILITADO

    @classmethod
    def is_obras_habilitado(cls) -> bool:
        """Indica se a seção 'Regime de Obras e Engenharia' deve ser exibida no formulário."""
        return cls.BLOCO_OBRAS_HABILITADO

    @classmethod
    def get_config_contexto(cls) -> Dict[str, Any]:
        """Retorna o dicionário de contexto pronto para uso nos templates e views."""
        return {
            'exibir_bloco_preposto': cls.is_preposto_habilitado(),
            'exibir_bloco_obras': cls.is_obras_habilitado(),
        }
