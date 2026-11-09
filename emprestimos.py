"""Controle local de empréstimos de equipamentos de um laboratório."""

import json
import os
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile


ARQUIVO_DADOS = Path(__file__).with_name("equipamentos.json")
ARQUIVO_TRAVA = ARQUIVO_DADOS.with_suffix(".lock")


def travar_sessao(arquivo):
    # O sistema operacional libera a trava ao fechar o arquivo ou encerrar o processo.
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(arquivo, fcntl.LOCK_EX | fcntl.LOCK_NB)


def carregar_equipamentos():
    try:
        with ARQUIVO_DADOS.open(encoding="utf-8") as arquivo:
            equipamentos = json.load(arquivo)
    except FileNotFoundError:
        return {}

    if not isinstance(equipamentos, dict):
        raise ValueError("O arquivo deve conter um objeto JSON.")

    for equipamento in equipamentos.values():
        if (
            not isinstance(equipamento, dict)
            or not isinstance(equipamento.get("nome"), str)
            or not isinstance(equipamento.get("emprestimos"), list)
        ):
            raise ValueError("Há um equipamento com estrutura inválida no arquivo.")
        for emprestimo in equipamento["emprestimos"]:
            if (
                not isinstance(emprestimo, dict)
                or not isinstance(emprestimo.get("responsavel"), str)
                or not isinstance(emprestimo.get("retirada"), str)
                or "devolucao" not in emprestimo
                or not isinstance(emprestimo["devolucao"], (str, type(None)))
            ):
                raise ValueError("Há um empréstimo com estrutura inválida no arquivo.")
    return equipamentos


def salvar_equipamentos(equipamentos):
    # Grava o conteúdo completo antes de substituir o arquivo anterior.
    caminho_temporario = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=ARQUIVO_DADOS.parent, delete=False
        ) as arquivo:
            caminho_temporario = Path(arquivo.name)
            json.dump(equipamentos, arquivo, ensure_ascii=False, indent=2)
            arquivo.write("\n")
        caminho_temporario.replace(ARQUIVO_DADOS)
    finally:
        if caminho_temporario is not None:
            caminho_temporario.unlink(missing_ok=True)


def ler_campo(rotulo):
    valor = input(rotulo).strip()
    if not valor:
        raise ValueError("O campo é obrigatório.")
    return valor


def emprestimo_ativo(equipamento):
    historico = equipamento["emprestimos"]
    if historico and historico[-1]["devolucao"] is None:
        return historico[-1]
    return None


def cadastrar(equipamentos):
    codigo = ler_campo("Código do equipamento: ").upper()
    if codigo in equipamentos:
        raise ValueError("Já existe um equipamento com esse código.")
    nome = ler_campo("Nome do equipamento: ")
    equipamentos[codigo] = {"nome": nome, "emprestimos": []}
    salvar_equipamentos(equipamentos)
    print("Equipamento cadastrado.")


def consultar(equipamentos):
    if not equipamentos:
        print("Nenhum equipamento cadastrado.")
        return

    for codigo, equipamento in sorted(equipamentos.items()):
        ativo = emprestimo_ativo(equipamento)
        situacao = "Disponível"
        if ativo is not None:
            situacao = f"Emprestado para {ativo['responsavel']} desde {ativo['retirada']}"
        print(f"{codigo} | {equipamento['nome']} | {situacao}")


def selecionar_equipamento(equipamentos):
    codigo = ler_campo("Código do equipamento: ").upper()
    if codigo not in equipamentos:
        raise ValueError("Equipamento não encontrado.")
    return equipamentos[codigo]


def emprestar(equipamentos):
    equipamento = selecionar_equipamento(equipamentos)
    if emprestimo_ativo(equipamento) is not None:
        raise ValueError("O equipamento já está emprestado.")

    responsavel = ler_campo("Nome do responsável: ")
    equipamento["emprestimos"].append(
        {"responsavel": responsavel, "retirada": date.today().isoformat(), "devolucao": None}
    )
    salvar_equipamentos(equipamentos)
    print("Empréstimo registrado.")


def devolver(equipamentos):
    equipamento = selecionar_equipamento(equipamentos)
    ativo = emprestimo_ativo(equipamento)
    if ativo is None:
        raise ValueError("O equipamento não tem empréstimo ativo.")

    ativo["devolucao"] = date.today().isoformat()
    salvar_equipamentos(equipamentos)
    print("Devolução registrada.")


def executar_menu():
    acoes = {"1": cadastrar, "2": consultar, "3": emprestar, "4": devolver}
    menu = (
        "\nControle de empréstimos\n"
        "1 - Cadastrar equipamento\n"
        "2 - Consultar equipamentos\n"
        "3 - Registrar empréstimo\n"
        "4 - Registrar devolução\n"
        "0 - Sair"
    )
    while True:
        try:
            print(menu)
            opcao = input("Opção: ").strip()
            if opcao == "0":
                return
            if opcao not in acoes:
                print("Opção inválida.")
                continue

            # Releitura a cada ação mantém a consulta fiel ao que foi salvo.
            try:
                equipamentos = carregar_equipamentos()
            except (OSError, ValueError) as erro:
                print(f"Não foi possível ler {ARQUIVO_DADOS.name}. {erro}")
                continue
            acoes[opcao](equipamentos)
        except ValueError as erro:
            print(erro)
        except OSError as erro:
            print(f"Não foi possível salvar os dados. {erro}")
        except (EOFError, KeyboardInterrupt):
            print("\nSessão encerrada.")
            return


if __name__ == "__main__":
    try:
        with ARQUIVO_TRAVA.open("a+b") as trava:
            travar_sessao(trava)
            executar_menu()
    except OSError as erro:
        print(f"Não foi possível iniciar a sessão. Feche outra instância, se houver. {erro}")
        raise SystemExit(1)
