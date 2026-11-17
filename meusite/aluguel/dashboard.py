# -*- coding: utf-8 -*-
"""Dashboard analítico e exportação de relatórios (CSV/PDF).

Gerado por patcher_dashboard.py — bloco idempotente.
"""

import calendar
import csv
import io
import re
from decimal import Decimal

from django.db.models import Sum
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from .models import Carrinho, Reserva, ReservaProduto

MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]

STATUS_LABEL = {
    "pendente": "Pendente",
    "confirmado": "Confirmado",
    "cancelado": "Cancelado",
}

STATUS_OPCOES = [("", "Todos os status")] + list(STATUS_LABEL.items())


# ---------------------------------------------------------------- helpers

def _admin_required(request):
    return bool(request.user.is_authenticated and request.user.is_staff)


def quantidade_carrinhos(reserva):
    texto = reserva.descricao or ""
    achado = re.search(r"Quantidade de carrinhos(?: solicitada)?:\s*(\d+)", texto, re.IGNORECASE)
    return max(1, int(achado.group(1))) if achado else 1


def _brl(valor):
    valor = Decimal(str(valor or 0))
    texto = "{:,.2f}".format(valor)
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def _financeiro(reserva):
    subtotal = Decimal(str(reserva.subtotal_sorvetes() or 0))
    unitario = Decimal(str(reserva.taxa_aluguel() or 0))
    aluguel = unitario * quantidade_carrinhos(reserva)
    return subtotal, aluguel, subtotal + aluguel


def _periodo(request):
    hoje = timezone.localdate()
    try:
        ano = int(request.GET.get("ano") or hoje.year)
    except (TypeError, ValueError):
        ano = hoje.year
    try:
        mes = int(request.GET.get("mes") or hoje.month)
    except (TypeError, ValueError):
        mes = hoje.month
    return ano, min(12, max(1, mes))


def _status(request):
    valor = (request.GET.get("status") or "").strip()
    return valor if valor in STATUS_LABEL else ""


def _queryset(ano, mes, status=""):
    qs = (
        Reserva.objects
        .filter(data_evento__year=ano, data_evento__month=mes)
        .select_related("id_cliente", "id_carrinho")
        .prefetch_related("itens__id_sorvete")
        .order_by("-data_evento", "-id")
    )
    if status:
        qs = qs.filter(status=status)
    return qs


def _dados_periodo(ano, mes, status=""):
    reservas = list(_queryset(ano, mes, status))
    confirmadas = [r for r in reservas if r.status == "confirmado"]
    pendentes = [r for r in reservas if r.status == "pendente"]
    canceladas = [r for r in reservas if r.status == "cancelado"]

    receita = sum((_financeiro(r)[2] for r in confirmadas), Decimal("0"))
    receita_pendente = sum((_financeiro(r)[2] for r in pendentes), Decimal("0"))
    ticket = receita / len(confirmadas) if confirmadas else Decimal("0")

    return {
        "reservas": reservas,
        "confirmadas": confirmadas,
        "pendentes": pendentes,
        "canceladas": canceladas,
        "receita": receita,
        "receita_pendente": receita_pendente,
        "ticket": ticket,
    }


def _serie_diaria(ano, mes, confirmadas, capacidade):
    total_dias = calendar.monthrange(ano, mes)[1]
    ocupados = {}
    for reserva in confirmadas:
        dia = reserva.data_evento.day
        ocupados[dia] = ocupados.get(dia, 0) + quantidade_carrinhos(reserva)

    serie = []
    for dia in range(1, total_dias + 1):
        qtd = ocupados.get(dia, 0)
        pct = round((qtd / capacidade) * 100) if capacidade else 0
        serie.append({"dia": dia, "ocupados": qtd, "percentual": min(100, pct)})
    return serie


def _top_sabores(reservas):
    ids = [r.id for r in reservas if r.status != "cancelado"]
    if not ids:
        return []
    return list(
        ReservaProduto.objects
        .filter(id_reserva_id__in=ids)
        .values("id_sorvete__nome_sorvete")
        .annotate(qtd=Sum("quantidade_escolhida"))
        .order_by("-qtd")[:8]
    )


# ---------------------------------------------------------------- views

def dashboard(request):
    if not _admin_required(request):
        return HttpResponseRedirect(reverse("painel"))

    ano, mes = _periodo(request)
    status = _status(request)
    dados = _dados_periodo(ano, mes, status)

    capacidade = Carrinho.objects.filter(status=True).count()
    serie = _serie_diaria(ano, mes, dados["confirmadas"], capacidade)

    ocupados_total = sum(d["ocupados"] for d in serie)
    ocupacao = (
        round((ocupados_total / (capacidade * len(serie))) * 100)
        if capacidade and serie else 0
    )

    tabela = []
    for reserva in dados["reservas"]:
        total = _financeiro(reserva)[2]
        tabela.append({
            "id": reserva.id,
            "data": reserva.data_evento.strftime("%d/%m/%Y"),
            "cliente": reserva.id_cliente.nome_cliente,
            "carrinhos": quantidade_carrinhos(reserva),
            "total": _brl(total),
            "status": reserva.status,
            "status_label": STATUS_LABEL.get(reserva.status, reserva.status),
        })

    anterior = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
    seguinte = (ano + 1, 1) if mes == 12 else (ano, mes + 1)

    contexto = {
        "ano": ano,
        "mes": mes,
        "mes_nome": MESES[mes - 1],
        "status": status,
        "status_opcoes": STATUS_OPCOES,
        "anterior": anterior,
        "seguinte": seguinte,
        "capacidade": capacidade,
        "serie": serie,
        "ocupacao": ocupacao,
        "dias_com_reserva": len([d for d in serie if d["ocupados"] > 0]),
        "top_sabores": _top_sabores(dados["reservas"]),
        "tabela": tabela,
        "receita_fmt": _brl(dados["receita"]),
        "receita_pendente_fmt": _brl(dados["receita_pendente"]),
        "ticket_fmt": _brl(dados["ticket"]),
        **dados,
    }
    return render(request, "aluguel/dashboard.html", contexto)


def exportar_csv(request):
    if not _admin_required(request):
        return HttpResponseRedirect(reverse("painel"))

    ano, mes = _periodo(request)
    status = _status(request)

    resposta = HttpResponse(content_type="text/csv; charset=utf-8")
    resposta["Content-Disposition"] = 'attachment; filename="reservas-%04d-%02d.csv"' % (ano, mes)
    resposta.write("\ufeff")

    escritor = csv.writer(resposta, delimiter=";")
    escritor.writerow([
        "ID", "Data", "Status", "Cliente", "Telefone", "E-mail",
        "Endereco", "Carrinhos", "Sabores", "Subtotal", "Aluguel", "Total", "Observacoes",
    ])

    for reserva in _queryset(ano, mes, status):
        subtotal, aluguel, total = _financeiro(reserva)
        sabores = ", ".join(
            "%dx %s" % (item.quantidade_escolhida, item.id_sorvete.nome_sorvete)
            for item in reserva.itens.all() if item.id_sorvete
        )
        escritor.writerow([
            reserva.id,
            reserva.data_evento.strftime("%d/%m/%Y"),
            STATUS_LABEL.get(reserva.status, reserva.status),
            reserva.id_cliente.nome_cliente,
            reserva.id_cliente.telefone or "",
            reserva.id_cliente.email or "",
            reserva.id_cliente.endereco or "",
            quantidade_carrinhos(reserva),
            sabores,
            str(subtotal).replace(".", ","),
            str(aluguel).replace(".", ","),
            str(total).replace(".", ","),
            (reserva.descricao or "").replace("\n", " "),
        ])

    return resposta


def exportar_pdf(request):
    if not _admin_required(request):
        return HttpResponseRedirect(reverse("painel"))

    ano, mes = _periodo(request)
    status = _status(request)
    dados = _dados_periodo(ano, mes, status)

    titulo = "Relatorio de reservas - %s/%s" % (MESES[mes - 1], ano)
    subtitulo = "Status: %s | Gerado em %s" % (
        STATUS_LABEL.get(status, "Todos"),
        timezone.localtime().strftime("%d/%m/%Y %H:%M"),
    )

    linhas = [
        "Reservas: %d | Confirmadas: %d | Pendentes: %d | Canceladas: %d" % (
            len(dados["reservas"]), len(dados["confirmadas"]),
            len(dados["pendentes"]), len(dados["canceladas"]),
        ),
        "Receita confirmada: %s | Receita pendente: %s | Ticket medio: %s" % (
            _brl(dados["receita"]), _brl(dados["receita_pendente"]), _brl(dados["ticket"]),
        ),
        "",
    ]

    for reserva in dados["reservas"]:
        subtotal, aluguel, total = _financeiro(reserva)
        linhas.append("#%d | %s | %s | %s | %d carrinho(s)" % (
            reserva.id,
            reserva.data_evento.strftime("%d/%m/%Y"),
            STATUS_LABEL.get(reserva.status, reserva.status),
            reserva.id_cliente.nome_cliente,
            quantidade_carrinhos(reserva),
        ))
        linhas.append("    Subtotal %s + Aluguel %s = Total %s" % (
            _brl(subtotal), _brl(aluguel), _brl(total),
        ))
        sabores = ", ".join(
            "%dx %s" % (i.quantidade_escolhida, i.id_sorvete.nome_sorvete)
            for i in reserva.itens.all() if i.id_sorvete
        )
        if sabores:
            linhas.append("    Sabores: " + sabores)

    resposta = HttpResponse(_gerar_pdf(titulo, subtitulo, linhas), content_type="application/pdf")
    resposta["Content-Disposition"] = 'attachment; filename="reservas-%04d-%02d.pdf"' % (ano, mes)
    return resposta


# ---------------------------------------------------------------- pdf

def _quebrar(texto, limite):
    texto = str(texto)
    if len(texto) <= limite:
        return [texto]
    pedacos = []
    while texto:
        pedacos.append(texto[:limite])
        texto = texto[limite:]
    return pedacos


def _gerar_pdf(titulo, subtitulo, linhas):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except Exception:
        return _pdf_fallback(titulo, subtitulo, linhas)

    buffer = io.BytesIO()
    doc = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4

    def cabecalho():
        doc.setFont("Helvetica-Bold", 13)
        doc.drawString(40, altura - 50, titulo[:90])
        doc.setFont("Helvetica", 8)
        doc.drawString(40, altura - 66, subtitulo[:120])
        doc.line(40, altura - 72, largura - 40, altura - 72)

    cabecalho()
    y = altura - 92
    doc.setFont("Helvetica", 8.5)

    for linha in linhas:
        for pedaco in _quebrar(linha, 105):
            if y < 60:
                doc.showPage()
                cabecalho()
                y = altura - 92
                doc.setFont("Helvetica", 8.5)
            doc.drawString(40, y, pedaco)
            y -= 12

    doc.showPage()
    doc.save()
    return buffer.getvalue()


def _pdf_fallback(titulo, subtitulo, linhas):
    def esc(valor):
        return (
            str(valor)
            .replace("\\", r"\\")
            .replace("(", r"\(")
            .replace(")", r"\)")
        )

    por_pagina = 44
    paginas = [linhas[i:i + por_pagina] for i in range(0, len(linhas), por_pagina)] or [[]]

    objetos = [b"", b"", b""]  # 1 catalogo, 2 paginas, 3 fonte

    def novo(conteudo):
        objetos.append(conteudo)
        return len(objetos)

    kids = []
    for pagina in paginas:
        corpo = ["BT", "/F1 14 Tf", "40 792 Td", "(%s) Tj" % esc(titulo[:95]), "ET"]
        corpo += ["BT", "/F1 8 Tf", "40 774 Td", "(%s) Tj" % esc(subtitulo[:130]), "ET"]
        corpo += ["BT", "/F1 9 Tf", "12 TL", "40 750 Td"]
        for linha in pagina:
            corpo.append("(%s) Tj T*" % esc(linha))
        corpo.append("ET")
        fluxo = "\n".join(corpo).encode("latin-1", "replace")

        num_conteudo = novo(b"<< /Length %d >>\nstream\n" % len(fluxo) + fluxo + b"\nendstream")
        num_pagina = novo((
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            "/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>" % num_conteudo
        ).encode("latin-1"))
        kids.append(num_pagina)

    objetos[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objetos[1] = ("<< /Type /Pages /Count %d /Kids [%s] >>" % (
        len(kids), " ".join("%d 0 R" % k for k in kids)
    )).encode("latin-1")
    objetos[2] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"

    saida = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for indice, objeto in enumerate(objetos, start=1):
        offsets.append(len(saida))
        saida += b"%d 0 obj\n" % indice + objeto + b"\nendobj\n"

    inicio_xref = len(saida)
    total = len(objetos) + 1
    saida += b"xref\n0 %d\n" % total
    saida += b"0000000000 65535 f \n"
    for deslocamento in offsets[1:]:
        saida += b"%010d 00000 n \n" % deslocamento
    saida += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (total, inicio_xref)

    return bytes(saida)
