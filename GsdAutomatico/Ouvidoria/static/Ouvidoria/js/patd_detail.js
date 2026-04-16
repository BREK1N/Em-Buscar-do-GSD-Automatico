// patd_detail.js — lê configuração do objeto PATD_CONFIG injetado pelo template
// Todas as variáveis Django são fornecidas via PATD_CONFIG (bridge definido no template).

const analiseData         = PATD_CONFIG.analiseData;
const assinaturasMilitar  = PATD_CONFIG.assinaturasMilitar;
let   documentPages       = PATD_CONFIG.documentPages;
const isSuperuser         = PATD_CONFIG.isSuperuser;
const isFinalized         = PATD_CONFIG.isFinalized;

const hasDefesaSig        = PATD_CONFIG.hasDefesaSig;
const defesaSigData       = PATD_CONFIG.defesaSigUrl;
const hasReconSig         = PATD_CONFIG.hasReconSig;
const reconSigData        = PATD_CONFIG.reconSigUrl;
const testemunha1SigData  = PATD_CONFIG.testemunha1SigUrl;
const testemunha2SigData  = PATD_CONFIG.testemunha2SigUrl;
const oficialSigData      = PATD_CONFIG.oficialSigUrl;
const comandanteSigData   = PATD_CONFIG.comandanteSigUrl;

let anexosDefesa                 = PATD_CONFIG.anexosDefesa;
let anexosReconsideracao         = PATD_CONFIG.anexosReconsideracao;
let anexosReconsideracaoOficial  = PATD_CONFIG.anexosReconsideracaoOficial;
let documentoFinalUrl            = PATD_CONFIG.documentoFinalUrl;

let signatureIndex = 0;

function createSignatureHtml(signatureUrl, altText, signatureType, signatureIndex) {
    let html = `<img class="signature-image-embedded" src="${signatureUrl}" alt="${altText}">`;
    if (isSuperuser && !isFinalized) {
        html += ` <button class="btn btn-sm btn-danger remove-signature-btn" data-signature-type="${signatureType}"`;
        if (signatureIndex !== undefined) {
            html += ` data-signature-index="${signatureIndex}"`;
        }
        html += ` title="Remover assinatura">(Remover)</button>`;
    }
    return html;
}

document.addEventListener('DOMContentLoaded', function() {
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    let isExpired = PATD_CONFIG.patdStatus === 'prazo_expirado';

    const deleteBtn = document.getElementById('delete-patd-btn');
    const deleteModal = document.getElementById('delete-modal');
    if (deleteBtn && deleteModal) {
        const cancelDeleteBtn = document.getElementById('cancel-delete-btn');
        deleteBtn.addEventListener('click', () => deleteModal.classList.add('active'));
        if(cancelDeleteBtn) cancelDeleteBtn.addEventListener('click', () => deleteModal.classList.remove('active'));
        deleteModal.addEventListener('click', (e) => {
            if (e.target === deleteModal) deleteModal.classList.remove('active');
        });
    }

    // --- LÓGICA DO MODAL DE FINALIZAÇÃO DA OUVIDORIA ---
    const finalizarCompletaModal = document.getElementById('finalizar-completa-modal');
    if (finalizarCompletaModal) {
        const openBtn = document.getElementById('btn-finalizar-completa-modal');
        const cancelBtn = document.getElementById('cancel-finalizar-completa-btn');
        const selectPunicao = document.getElementById('id_tipo_punicao_final');
        const divDias = document.getElementById('div_dias_final');
        const inputDias = document.getElementById('id_dias_final');
        const divMotivo = document.getElementById('div_motivo_final');
        const inputMotivo = document.getElementById('id_motivo_final');

        if(openBtn) {
            openBtn.addEventListener('click', () => finalizarCompletaModal.classList.add('active'));
        }
        if(cancelBtn) {
            cancelBtn.addEventListener('click', () => finalizarCompletaModal.classList.remove('active'));
        }
        finalizarCompletaModal.addEventListener('click', e => {
            if (e.target === finalizarCompletaModal) finalizarCompletaModal.classList.remove('active');
        });

        if(selectPunicao) {
            selectPunicao.addEventListener('change', (e) => {
                const val = e.target.value;

                if (val === 'detenção' || val === 'prisão') {
                    divDias.style.display = 'block';
                    inputDias.required = true;
                } else {
                    divDias.style.display = 'none';
                    inputDias.required = false;
                }

                if (val === 'justificada') {
                    divMotivo.style.display = 'block';
                    inputMotivo.required = true;
                } else {
                    divMotivo.style.display = 'none';
                    inputMotivo.required = false;
                }
            });
        }
    }

    // --- LÓGICA DO MODAL GENÉRICO DE ASSINATURA ---
    const signatureModal = document.getElementById('signature-modal-generic');
    if (signatureModal) {
        const canvas = document.getElementById('signature-canvas-generic');
        const signaturePad = new SignaturePad(canvas, { backgroundColor: 'rgb(255, 255, 255)' });
        let currentSignatureConfig = {};

        function resizeCanvas() {
            const ratio = Math.max(window.devicePixelRatio || 1, 1);
            const parentWidth = canvas.parentElement.offsetWidth;
            canvas.width = parentWidth * ratio;
            canvas.height = canvas.offsetHeight * ratio;
            canvas.getContext("2d").scale(ratio, ratio);
            signaturePad.clear();
        }

        document.body.addEventListener('click', function(e) {
            if (isFinalized) return;

            const btn = e.target.closest('.open-signature-modal');
            if (btn) {
                const type = btn.dataset.type;
                currentSignatureConfig = { type };

                const modalTitle = signatureModal.querySelector('#signature-modal-title');
                const modalParagraph = signatureModal.querySelector('#signature-modal-prompt');

                if (type === 'ciencia') {
                    currentSignatureConfig.index = parseInt(btn.dataset.index, 10);
                    modalTitle.textContent = 'Registrar Ciência da Acusação';
                    modalParagraph.textContent = `Eu, ${PATD_CONFIG.militarNome}, declaro ter ciência dos fatos a mim imputados (Assinatura ${currentSignatureConfig.index + 1}).`;
                } else if (type === 'defesa') {
                    modalTitle.textContent = 'Assinar Alegação de Defesa';
                    modalParagraph.textContent = 'Confirmo que esta é a minha alegação de defesa.';
                } else if (type === 'reconsideracao') {
                    modalTitle.textContent = 'Assinar Pedido de Reconsideração';
                    modalParagraph.textContent = 'Confirmo que este é o meu pedido de reconsideração.';
                } else if (type === 'oficial') {
                    modalTitle.textContent = 'Assinatura do Oficial Apurador';
                    modalParagraph.textContent = 'Desenhe a assinatura no campo abaixo.';
                } else if (type === 'testemunha') {
                    currentSignatureConfig.num = btn.dataset.testemunhaNum;
                    modalTitle.textContent = `Assinatura da ${currentSignatureConfig.num}ª Testemunha`;
                    modalParagraph.textContent = 'A testemunha deve desenhar a assinatura no campo abaixo.';
                }

                signatureModal.classList.add('active');
                resizeCanvas();
            }
        });

        document.getElementById('cancel-signature-btn-generic').addEventListener('click', () => signatureModal.classList.remove('active'));
        document.getElementById('clear-signature-btn-generic').addEventListener('click', () => signaturePad.clear());
        document.getElementById('save-signature-btn-generic').addEventListener('click', () => {
            if (signaturePad.isEmpty()) {
                alert("Por favor, forneça a assinatura.");
                return;
            }
            let url, body;
            const signatureData = signaturePad.toDataURL('image/jpeg', 0.5);

            switch (currentSignatureConfig.type) {
                case 'ciencia':
                    url = PATD_CONFIG.urls.salvarAssinaturaCiencia;
                    body = JSON.stringify({ signature_data: signatureData, assinatura_index: currentSignatureConfig.index });
                    break;
                case 'defesa':
                    url = PATD_CONFIG.urls.salvarAssinaturaDefesa;
                    body = JSON.stringify({ signature_data: signatureData });
                    break;
                case 'reconsideracao':
                    url = PATD_CONFIG.urls.salvarAssinaturaReconsideracao;
                    body = JSON.stringify({ signature_data: signatureData });
                    break;
                case 'oficial':
                    url = PATD_CONFIG.urls.salvarAssinatura;
                    body = JSON.stringify({ signature_data: signatureData });
                    break;
                case 'testemunha':
                    url = `/Ouvidoria/patd/${PATD_CONFIG.patdPk}/salvar_assinatura_testemunha/${currentSignatureConfig.num}/`;
                    body = JSON.stringify({ signature_data: signatureData });
                    break;
                default:
                    return;
            }

            fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: body
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') window.location.reload();
                else alert('Erro: ' + data.message);
            })
            .catch(error => console.error('Erro:', error));
        });

        const importSignatureBtn = document.getElementById('import-signature-btn');
        const pasteSignatureBtn = document.getElementById('paste-signature-btn');
        const signatureFileInput = document.getElementById('signature-file-input');

        if (importSignatureBtn && signatureFileInput) {
            importSignatureBtn.addEventListener('click', () => {
                signatureFileInput.click();
            });

            signatureFileInput.addEventListener('change', (event) => {
                const file = event.target.files[0];
                if (file && file.type.startsWith('image/')) {
                    const reader = new FileReader();
                    reader.onload = (e) => {
                        signaturePad.fromDataURL(e.target.result, {
                            width: canvas.width,
                            height: canvas.height
                        });
                    };
                    reader.readAsDataURL(file);
                } else {
                    alert('Por favor, selecione um ficheiro de imagem válido.');
                }
                signatureFileInput.value = '';
            });
        }

        if (pasteSignatureBtn) {
            pasteSignatureBtn.addEventListener('click', async () => {
                try {
                    const permission = await navigator.permissions.query({ name: 'clipboard-read' });
                    if (permission.state === 'denied') {
                        throw new Error('A permissão para aceder à área de transferência foi negada.');
                    }

                    const clipboardItems = await navigator.clipboard.read();
                    const imageItem = clipboardItems.find(item => item.types.some(type => type.startsWith('image/')));

                    if (imageItem) {
                        const imageType = imageItem.types.find(type => type.startsWith('image/'));
                        const blob = await imageItem.getType(imageType);
                        const reader = new FileReader();
                        reader.onload = (e) => {
                            signaturePad.fromDataURL(e.target.result, {
                                width: canvas.width,
                                height: canvas.height
                            });
                        };
                        reader.readAsDataURL(blob);
                    } else {
                        alert('Nenhuma imagem encontrada na área de transferência. Por favor, copie uma imagem primeiro.');
                    }
                } catch (error) {
                    console.error('Erro ao colar da área de transferência:', error);
                    alert('Não foi possível colar a imagem. Verifique as permissões da área de transferência do seu navegador ou tente usar um navegador compatível. ' + error.message);
                }
            });
        }
    }

    const aceitarAtribuicaoModal = document.getElementById('aceitar-atribuicao-modal');
    if (aceitarAtribuicaoModal) {
        const openBtn = document.getElementById('btn-aceitar-atribuicao-modal');
        const cancelBtn = document.getElementById('cancel-aceitar-btn');
        if(openBtn) {
            openBtn.addEventListener('click', () => aceitarAtribuicaoModal.classList.add('active'));
        }
        if(cancelBtn) cancelBtn.addEventListener('click', () => aceitarAtribuicaoModal.classList.remove('active'));
        aceitarAtribuicaoModal.addEventListener('click', e => {
            if (e.target === aceitarAtribuicaoModal) aceitarAtribuicaoModal.classList.remove('active');
        });
    }

    const avancarModal = document.getElementById('avancar-modal');
    if (avancarModal) {
        const openBtn = document.getElementById('btn-avancar-comandante');
        const cancelBtn = document.getElementById('cancel-avancar-btn');
        if(openBtn) {
            openBtn.addEventListener('click', () => avancarModal.classList.add('active'));
        }
        if(cancelBtn) {
            cancelBtn.addEventListener('click', () => avancarModal.classList.remove('active'));
        }
        avancarModal.addEventListener('click', e => {
            if (e.target === avancarModal) avancarModal.classList.remove('active');
        });

        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.has('erro') && urlParams.get('erro') === 'testemunhas') {
            alert('Erro: Não é possível avançar. As duas testemunhas devem ser definidas na aba "Editar".');
            window.history.replaceState({}, document.title, window.location.pathname);
        }
    }

    const retornarModal = document.getElementById('retornar-patd-modal');
    if (retornarModal) {
        const cancelBtn = document.getElementById('cancel-retornar-btn');
        if(cancelBtn) {
            cancelBtn.addEventListener('click', () => retornarModal.classList.remove('active'));
        }
        retornarModal.addEventListener('click', e => {
            if (e.target === retornarModal) retornarModal.classList.remove('active');
        });

        document.body.addEventListener('click', function(e) {
            const target = e.target.closest('.open-retornar-modal-btn');
            if (target) {
                const patdPk = target.dataset.patdPk;
                const patdNumero = target.dataset.patdNumero;
                const form = document.getElementById('retornar-patd-form');
                const title = document.getElementById('retornar-modal-title');

                if (form && title) {
                    form.action = `/Ouvidoria/patd/${patdPk}/retornar/`;
                    title.textContent = `Retornar PATD Nº ${patdNumero}`;
                    retornarModal.classList.add('active');
                }
            }
        });
    }

    const reconsideracaoModal = document.getElementById('reconsideracao-modal');
    const reconsideracaoTextoModal = document.getElementById('reconsideracao-texto-modal');

    if (reconsideracaoModal && reconsideracaoTextoModal) {
        const openBtn = document.getElementById('btn-reconsideracao-modal');
        const cancelBtn = document.getElementById('cancel-reconsideracao-btn');
        const confirmBtn = document.getElementById('confirm-reconsideracao-btn');

        const cancelTextoBtn = document.getElementById('cancel-reconsideracao-texto-btn');
        const submitTextoBtn = document.getElementById('submit-reconsideracao-texto-btn');

        if(openBtn) {
            openBtn.addEventListener('click', () => reconsideracaoModal.classList.add('active'));
        }
        if(cancelBtn) {
            cancelBtn.addEventListener('click', () => reconsideracaoModal.classList.remove('active'));
        }
        if(confirmBtn) {
            confirmBtn.addEventListener('click', () => {
                const url = PATD_CONFIG.urls.solicitarReconsideracao;
                fetch(url, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': csrfToken }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        reconsideracaoModal.classList.remove('active');
                        reconsideracaoTextoModal.classList.add('active');
                    } else {
                        alert('Erro: ' + data.message);
                    }
                })
                .catch(error => console.error('Erro:', error));
            });
        }

        if(cancelTextoBtn) {
            cancelTextoBtn.addEventListener('click', () => reconsideracaoTextoModal.classList.remove('active'));
        }

        document.body.addEventListener('click', e => {
            if (e.target && e.target.id === 'add-reconsideracao-texto-btn-doc') {
                reconsideracaoTextoModal.classList.add('active');
            }
        });

        if(submitTextoBtn) {
            submitTextoBtn.addEventListener('click', () => {
                const form = document.getElementById('form-reconsideracao');
                const formData = new FormData(form);
                const url = PATD_CONFIG.urls.salvarReconsideracao;

                fetch(url, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': csrfToken },
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        window.location.reload();
                    } else {
                        alert('Erro: ' + data.message);
                    }
                })
                .catch(error => console.error('Erro:', error));
            });
        }
    }

    const defesaModal = document.getElementById('defesa-modal');
    if (defesaModal) {
        const addDefesaBtn = document.getElementById('add-defesa-btn');
        const confirmDefesaModal = document.getElementById('confirm-defesa-modal');
        const cancelDefesaBtn = document.getElementById('cancel-defesa-btn');
        const submitDefesaBtn = document.getElementById('submit-defesa-btn');
        const cancelConfirmDefesaBtn = document.getElementById('cancel-confirm-defesa-btn');
        const finalSubmitDefesaBtn = document.getElementById('final-submit-defesa-btn');
        const formDefesa = document.getElementById('form-alegacao-defesa');

        function openDefesaModal() {
            defesaModal.classList.add('active');
        }

        if (addDefesaBtn) addDefesaBtn.addEventListener('click', openDefesaModal);
        document.body.addEventListener('click', e => {
            if (e.target && e.target.id === 'add-defesa-btn-doc') openDefesaModal();
        });

        if(cancelDefesaBtn) cancelDefesaBtn.addEventListener('click', () => defesaModal.classList.remove('active'));
        if(submitDefesaBtn) submitDefesaBtn.addEventListener('click', () => {
            const alegacaoText = document.getElementById('alegacao-defesa-texto').value;
            const anexosInput = document.getElementById('anexos_defesa');
            if (alegacaoText.trim() === "" && anexosInput.files.length === 0) {
                alert("É necessário fornecer um texto ou anexar pelo menos um ficheiro.");
                return;
            }
            defesaModal.classList.remove('active');
            if(confirmDefesaModal) confirmDefesaModal.classList.add('active');
        });

        if(cancelConfirmDefesaBtn) cancelConfirmDefesaBtn.addEventListener('click', () => confirmDefesaModal.classList.remove('active'));

        if(finalSubmitDefesaBtn) finalSubmitDefesaBtn.addEventListener('click', () => {
            const formData = new FormData(formDefesa);
            const url = PATD_CONFIG.urls.salvarAlegacaoDefesa;

            fetch(url, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrfToken },
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') window.location.reload();
                else alert('Erro: ' + data.message);
            })
            .catch(error => console.error('Erro:', error));
        });
    }

    const extenderPrazoModal = document.getElementById('extender-prazo-modal');
    const extenderPrazoBtn = document.getElementById('extender-prazo-btn');
    const prosseguirBtn = document.getElementById('prosseguir-sem-defesa-btn');
    function handleProsseguirSemAlegacao() {
        if (confirm('Tem certeza que deseja prosseguir sem a alegação de defesa? Esta ação registrará a preclusão e não poderá ser desfeita.')) {
            const url = PATD_CONFIG.urls.prosseguirSemAlegacao;
            fetch(url, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrfToken }
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') window.location.reload();
                else alert('Erro: ' + data.message);
            })
            .catch(error => console.error('Erro:', error));
        }
    }
    if (extenderPrazoBtn) {
        extenderPrazoBtn.addEventListener('click', () => extenderPrazoModal.classList.add('active'));
    }
    if (prosseguirBtn) {
        prosseguirBtn.addEventListener('click', handleProsseguirSemAlegacao);
    }
    if (extenderPrazoModal) {
        const cancelExtenderBtn = document.getElementById('cancel-extender-prazo-btn');
        if(cancelExtenderBtn) cancelExtenderBtn.addEventListener('click', () => extenderPrazoModal.classList.remove('active'));

        const extenderForm = document.getElementById('extender-prazo-form');
        if(extenderForm) extenderForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const dias = document.getElementById('extender-dias').value;
            const minutosInput = document.getElementById('extender-minutos');
            const minutos = minutosInput ? minutosInput.value : 0;
            const url = PATD_CONFIG.urls.extenderPrazo;
            fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({ 'dias': dias, 'minutos': minutos })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') window.location.reload();
                else alert('Erro: ' + data.message);
            })
            .catch(error => console.error('Erro:', error));
        });
    }

    const countdownTimer = document.getElementById('countdown-timer');
    const prazoBox = document.getElementById('prazo-box');
    if (countdownTimer && PATD_CONFIG.dataCiencia) {
        const dataCiencia = new Date(PATD_CONFIG.dataCienciaIso);
        const prazoDias = PATD_CONFIG.prazoDefesaDias || 0;

        function addBusinessDays(startDate, days) {
            let currentDate = new Date(startDate);
            let addedDays = 0;
            while (addedDays < days) {
                currentDate.setDate(currentDate.getDate() + 1);
                if (currentDate.getDay() !== 0 && currentDate.getDay() !== 6) {
                    addedDays++;
                }
            }
            return currentDate;
        }
        let deadlineDate = addBusinessDays(dataCiencia, prazoDias);
        let deadline = new Date(deadlineDate.getFullYear(), deadlineDate.getMonth(), deadlineDate.getDate() + 1);

        const interval = setInterval(() => {
            const now = new Date();
            const diff = deadline - now;
            if (diff <= 0) {
                countdownTimer.textContent = "Prazo expirado.";
                if(prazoBox) prazoBox.classList.add('expirado');
                clearInterval(interval);
                if (!isExpired) {
                    isExpired = true;
                    showExpiredButtons();
                }
                return;
            }
            const d = Math.floor(diff / (1000 * 60 * 60 * 24));
            const h = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
            const m = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
            const s = Math.floor((diff % (1000 * 60)) / 1000);
            countdownTimer.textContent = `${d}d ${h}h ${m}m ${s}s`;
        }, 1000);
    }

    const reconsideracaoCountdownTimer = document.getElementById('reconsideracao-countdown-timer');
    const reconsideracaoPrazoBox = document.getElementById('reconsideracao-prazo-box');
    if (reconsideracaoCountdownTimer && PATD_CONFIG.dataPublicacaoPunicao) {
        const dataPublicacao = new Date(PATD_CONFIG.dataPublicacaoPunicaoIso);
        const prazoDias = 15;
        const deadline = new Date(dataPublicacao.getTime() + prazoDias * 24 * 60 * 60 * 1000);

        const interval = setInterval(() => {
            const now = new Date();
            const diff = deadline - now;

            if (diff <= 0) {
                reconsideracaoCountdownTimer.textContent = "Prazo expirado.";
                if(reconsideracaoPrazoBox) reconsideracaoPrazoBox.classList.add('expirado');
                clearInterval(interval);
                fetch(PATD_CONFIG.urls.verificarPrazos, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    },
                    body: JSON.stringify({})
                });
                return;
            }
            const d = Math.floor(diff / (1000 * 60 * 60 * 24));
            const h = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
            const m = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
            const s = Math.floor((diff % (1000 * 60)) / 1000);
            reconsideracaoCountdownTimer.textContent = `${d}d ${h}h ${m}m ${s}s`;
        }, 1000);
    }

    function showExpiredButtons() {
        const actionsContainer = document.getElementById('form-actions-container');
        const addDefesaBtn = document.getElementById('add-defesa-btn');
        const statusElement = document.getElementById('patd-status');
        if (addDefesaBtn) addDefesaBtn.remove();
        if (statusElement) statusElement.textContent = "Prazo expirado";
        if (!document.getElementById('extender-prazo-btn')) {
            const extenderBtn = document.createElement('button');
            extenderBtn.type = 'button';
            extenderBtn.className = 'btn btn-warning';
            extenderBtn.id = 'extender-prazo-btn';
            extenderBtn.textContent = 'Extender Prazo';
            extenderBtn.addEventListener('click', () => extenderPrazoModal.classList.add('active'));
            actionsContainer.insertBefore(extenderBtn, actionsContainer.firstChild);
        }
        if (!document.getElementById('prosseguir-sem-defesa-btn')) {
            const prosseguirBtn = document.createElement('button');
            prosseguirBtn.type = 'button';
            prosseguirBtn.className = 'btn btn-danger';
            prosseguirBtn.id = 'prosseguir-sem-defesa-btn';
            prosseguirBtn.textContent = 'Prosseguir sem Alegação';
            prosseguirBtn.addEventListener('click', handleProsseguirSemAlegacao);
            const extenderBtn = document.getElementById('extender-prazo-btn');
            if (extenderBtn) extenderBtn.insertAdjacentElement('afterend', prosseguirBtn);
            else actionsContainer.insertBefore(prosseguirBtn, actionsContainer.firstChild);
        }
    }

    const tabLinks = document.querySelectorAll('.tab-link');
    const tabPanels = document.querySelectorAll('.tab-panel');

    tabLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            tabLinks.forEach(l => l.classList.remove('active'));
            tabPanels.forEach(p => p.classList.remove('active'));
            link.classList.add('active');

            const targetPanel = document.getElementById(link.dataset.target);
            if (targetPanel) {
                targetPanel.classList.add('active');

                const sigNavButton = document.getElementById('signature-nav-button');
                if (link.dataset.target === 'tab-visualizador') {
                    renderVisualizador();
                } else {
                    if (sigNavButton) sigNavButton.style.display = 'none';
                }
            }
            localStorage.setItem(`activePatdTab-${PATD_CONFIG.patdPk}`, link.dataset.target);
        });
    });

    function generateEmbeddedAnexoHTML(anexo) {
        const fileType = anexo.tipo_arquivo;
        return `
            <div class="embedded-anexo-item">
                <div class="embedded-anexo-link">
                    <h4>${anexo.nome}</h4>
                    <p>Anexo (.${fileType}). Clique abaixo para abrir ou baixar.</p>
                    <a href="${anexo.url}" class="btn-download" target="_blank" rel="noopener noreferrer">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" style="width: 16px; height: 16px;"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" /></svg>
                        Abrir/Baixar Anexo
                    </a>
                </div>
            </div>
        `;
    }

    function generateEmbeddedAnexosGroup(anexos, title) {
        if (!anexos || anexos.length === 0) return '';
        let itemsHtml = anexos.map(generateEmbeddedAnexoHTML).join('');
        return `
            <div class="embedded-anexo-container">
                <h3 class="embedded-anexo-header">${title}</h3>
                ${itemsHtml}
            </div>
        `;
    }

    function processPlaceholders(text) {
        let processedHtml = text;

        processedHtml = processedHtml.replace(/{Botao Adicionar Alegacao}/g, `<button id="add-defesa-btn-doc" class="btn btn-sm btn-primary">Adicionar Alegação de Defesa</button>`);
        processedHtml = processedHtml.replace(/{Botao Adicionar Reconsideracao}/g, `<button id="add-reconsideracao-texto-btn-doc" class="btn btn-sm btn-primary">Adicionar Texto de Reconsideração</button>`);

        processedHtml = processedHtml.replace(/{ANEXOS_DEFESA_PLACEHOLDER}/g, generateEmbeddedAnexosGroup(anexosDefesa, "Anexos da Alegação de Defesa"));
        processedHtml = processedHtml.replace(/{ANEXOS_RECONSIDERACAO_PLACEHOLDER}/g, generateEmbeddedAnexosGroup(anexosReconsideracao, "Anexos da Reconsideração"));
        processedHtml = processedHtml.replace(/{ANEXO_OFICIAL_RECONSIDERACAO_PLACEHOLDER}/g, generateEmbeddedAnexosGroup(anexosReconsideracaoOficial, "Anexo do Oficial (Reconsideração)"));

        processedHtml = processedHtml.replace(/{Assinatura Alegacao Defesa}/g, hasDefesaSig ? createSignatureHtml(defesaSigData, 'Assinatura da Defesa', 'defesa') : `<button class="btn btn-sm btn-success open-signature-modal" data-type="defesa">Assinar Alegação de Defesa</button>`);
        processedHtml = processedHtml.replace(/{Assinatura Reconsideracao}/g, hasReconSig ? createSignatureHtml(reconSigData, 'Assinatura da Reconsideração', 'reconsideracao') : `<button class="btn btn-sm btn-success open-signature-modal" data-type="reconsideracao">Assinar Reconsideração</button>`);

        processedHtml = processedHtml.replace(/{Assinatura_Imagem_Oficial_Apurador}/g, oficialSigData ? createSignatureHtml(oficialSigData, 'Assinatura do Oficial Apurador', 'oficial') : '[Sem assinatura]');
        processedHtml = processedHtml.replace(/{Assinatura_Imagem_Comandante_GSD}/g, comandanteSigData ? `<img class="signature-image-embedded" src="${comandanteSigData}" alt="Assinatura do Comandante">` : '[Sem assinatura]');
        processedHtml = processedHtml.replace(/{Assinatura_Imagem_Testemunha_1}/g, testemunha1SigData ? createSignatureHtml(testemunha1SigData, 'Assinatura da Testemunha 1', 'testemunha1') : '[Sem assinatura]');
        processedHtml = processedHtml.replace(/{Assinatura_Imagem_Testemunha_2}/g, testemunha2SigData ? createSignatureHtml(testemunha2SigData, 'Assinatura da Testemunha 2', 'testemunha2') : '[Sem assinatura]');

        processedHtml = processedHtml.replace(/{Assinatura Militar Arrolado}/g, () => {
            const index = signatureIndex++;
            if (assinaturasMilitar[index]) {
                return createSignatureHtml(assinaturasMilitar[index], `Assinatura ${index + 1}`, 'ciencia', index);
            } else {
                return `<button class="btn btn-sm btn-success open-signature-modal" data-type="ciencia" data-index="${index}">Assinar</button>`;
            }
        });

        processedHtml = processedHtml.replace(/{Botao Assinar Oficial}/g, `<button class="btn btn-sm btn-success open-signature-modal" data-type="oficial">Assinar</button>`);
        processedHtml = processedHtml.replace(/{Botao Assinar Testemunha 1}/g, `<button class="btn btn-sm btn-success open-signature-modal" data-type="testemunha" data-testemunha-num="1">Assinar (Testemunha 1)</button>`);
        processedHtml = processedHtml.replace(/{Botao Assinar Testemunha 2}/g, `<button class="btn btn-sm btn-success open-signature-modal" data-type="testemunha" data-testemunha-num="2">Assinar (Testemunha 2)</button>`);

        processedHtml = processedHtml.replace(/\[Sem assinatura\]/g, '<span class="no-signature-text">[Sem assinatura]</span>');
        processedHtml = processedHtml.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        return processedHtml;
    }

    const pageContainer = document.getElementById('document-preview-container');
    pageContainer.addEventListener('change', function(e) {
        if (e.target.classList.contains('editable-date')) {
            scheduleSave();
        }
    });
    pageContainer.addEventListener('input', function(e) {
        if (e.target.classList.contains('editable-text')) {
            scheduleSave();
        }
    });

    let pendingSignatureElements = [];
    let currentSignatureIndex = -1;
    let saveTimeout;

    function scheduleSave() {
        if (isFinalized) {
            console.log("Processo finalizado. Alterações ignoradas.");
            return;
        }

        clearTimeout(saveTimeout);
        saveTimeout = setTimeout(() => {
            saveDocumentChanges();
        }, 1500);
    }

    function saveDocumentChanges() {
        if (!pageContainer) return;

        const dates = {};
        pageContainer.querySelectorAll('.editable-date').forEach(input => {
            const fieldName = input.dataset.dateField;
            if (fieldName) dates[fieldName] = input.value;
        });

        const texts = {};
        pageContainer.querySelectorAll('.editable-text').forEach(input => {
            const fieldName = input.dataset.textField;
            if (fieldName) texts[fieldName] = input.value;
        });

        const tempContainer = pageContainer.cloneNode(true);

        const datePlaceholders = {
            'data_ocorrencia': '{data da Ocorrencia}',
            'data_oficio': '{data_oficio}',
            'data_ciencia': '{data ciência}',
            'data_alegacao': '{Data da alegação}',
            'data_publicacao_punicao': '{data_publicacao_punicao}',
            'data_reconsideracao': '{Data_reconsideracao}',
        };

        tempContainer.querySelectorAll('.editable-date').forEach(input => {
            const fieldName = input.dataset.dateField;
            const placeholder = datePlaceholders[fieldName];
            if (placeholder) {
                input.replaceWith(document.createTextNode(placeholder));
            }
        });

        tempContainer.querySelectorAll('.editable-text').forEach(input => {
            const fieldName = input.dataset.textField;
            if (fieldName === 'localidade') {
                input.replaceWith(document.createTextNode('{Localidade}'));
            }
        });

        const signaturePlaceholders = {
            'Assinatura da Defesa': '{Assinatura Alegacao Defesa}',
            'Assinatura da Reconsideração': '{Assinatura Reconsideracao}',
            'Assinatura da Testemunha 1': '{Assinatura_Imagem_Testemunha_1}',
            'Assinatura da Testemunha 2': '{Assinatura_Imagem_Testemunha_2}',
            'Assinatura do Oficial Apurador': '{Assinatura_Imagem_Oficial_Apurador}',
            'Assinatura do Comandante': '{Assinatura_Imagem_Comandante_GSD}'
        };

        tempContainer.querySelectorAll('img.signature-image-embedded').forEach(img => {
            let alt = img.getAttribute('alt');
            let placeholder = signaturePlaceholders[alt] || '{Assinatura Militar Arrolado}';
            if (alt && alt.startsWith('Assinatura ')) {
                placeholder = '{Assinatura Militar Arrolado}';
            }
            img.replaceWith(document.createTextNode(placeholder));
        });

        tempContainer.querySelectorAll('button.open-signature-modal').forEach(btn => {
            const type = btn.dataset.type;
            let placeholder = '';
            if (type === 'ciencia') placeholder = '{Assinatura Militar Arrolado}';
            else if (type === 'defesa') placeholder = '{Assinatura Alegacao Defesa}';
            else if (type === 'reconsideracao') placeholder = '{Assinatura Reconsideracao}';
            else if (type === 'oficial') placeholder = '{Botao Assinar Oficial}';
            else if (type === 'testemunha') placeholder = `{Botao Assinar Testemunha ${btn.dataset.testemunhaNum}}`;
            btn.replaceWith(document.createTextNode(placeholder));
        });

        tempContainer.querySelectorAll('button#add-defesa-btn-doc').forEach(btn => btn.replaceWith(document.createTextNode('{Botao Adicionar Alegacao}')));
        tempContainer.querySelectorAll('button#add-reconsideracao-texto-btn-doc').forEach(btn => btn.replaceWith(document.createTextNode('{Botao Adicionar Reconsideracao}')));

        tempContainer.querySelectorAll('.embedded-anexo-container').forEach(container => {
            const header = container.querySelector('.embedded-anexo-header');
            let placeholder = '';
            if (header) {
                if (header.textContent.includes("Defesa")) placeholder = '{ANEXOS_DEFESA_PLACEHOLDER}';
                else if (header.textContent.includes("Reconsideração")) placeholder = '{ANEXOS_RECONSIDERACAO_PLACEHOLDER}';
                else if (header.textContent.includes("Oficial")) placeholder = '{ANEXO_OFICIAL_RECONSIDERACAO_PLACEHOLDER}';
            }
            container.replaceWith(document.createTextNode(placeholder));
        });

        const pageDelimiter = `PATD Nº ${PATD_CONFIG.numeroPATD}/BAGL-GSDGL/${PATD_CONFIG.dataInicioDmy}`;
        let fullContent = [];

        tempContainer.querySelectorAll('.page .page-content').forEach(contentDiv => {
            let pageContent = [];
            contentDiv.childNodes.forEach(node => {
                if (node.nodeType === Node.TEXT_NODE) {
                    pageContent.push(node.textContent.trim());
                } else if (node.nodeType === Node.ELEMENT_NODE && node.tagName === 'P') {
                    let cleanText = node.innerHTML.replace(/<br\s*\/?>/gi, '\n');
                    cleanText = cleanText.replace(/&nbsp;/g, ' ');
                    cleanText = cleanText.replace(/<strong>(.*?)<\/strong>/g, '**$1**');

                    const tempDiv = document.createElement('div');
                    tempDiv.innerHTML = cleanText;
                    pageContent.push(tempDiv.textContent || tempDiv.innerText || '');
                }
            });
            fullContent.push(pageContent.join('\n'));
        });

        const newDocumentText = fullContent.join(`\n${pageDelimiter}\n`);

        const url = PATD_CONFIG.urls.salvarDocumento;
        fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
            body: JSON.stringify({
                'texto_documento': newDocumentText,
                'dates': dates,
                'texts': texts
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                console.log("Documento e datas salvos automaticamente.");
            } else {
                alert('Erro: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Erro:', error)
        });
    }

    function renderVisualizador() {
        if (!pageContainer) return;

        if (documentoFinalUrl) {
            pageContainer.style.padding = '0';
            pageContainer.style.backgroundColor = 'transparent';
            pageContainer.style.boxShadow = 'none';

            if (documentoFinalUrl.toLowerCase().endsWith('.pdf')) {
                pageContainer.innerHTML = `<iframe src="${documentoFinalUrl}#view=FitH" width="100%" height="800px" style="border:none; border-radius: 8px;"></iframe>`;
            } else {
                pageContainer.innerHTML = `
                    <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; min-height: 400px; color: var(--text-primary); text-align: center; background-color: var(--bg-content); border-radius: 8px; border: 1px solid var(--border-color);">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" style="width: 64px; height: 64px; color: var(--accent-color); margin-bottom: 20px;">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m.75 12.75h.008M8.25 15h.008M8.25 18h.008m3.75-12h.008m2.25-3h.008M12 6h.008m-2.25 6h.008m2.25 6h.008M12 18h.008m-3.75-6h.008m2.25-6h.008" />
                        </svg>
                        <h3>Documento Final Anexado (.docx/.doc)</h3>
                        <p style="color: var(--text-secondary); margin-bottom: 20px;">O arquivo final foi salvo em formato Word e não pode ser renderizado nativamente no navegador.</p>
                        <a href="${documentoFinalUrl}" class="btn btn-primary" target="_blank" download>
                            Baixar Documento Final
                        </a>
                    </div>
                `;
            }

            const sigNavButton = document.getElementById('signature-nav-button');
            if (sigNavButton) sigNavButton.style.display = 'none';
            return;
        }

        pageContainer.innerHTML = '';
        signatureIndex = 0;
        let pageCounter = 1;

        if (!documentPages || documentPages.length === 0) {
            pageContainer.innerHTML = '<p style="text-align: center; color: var(--text-secondary);">O conteúdo do documento está vazio ou não pôde ser carregado.</p>';
            return;
        }

        documentPages.forEach((docHtml, docIndex) => {
            const logicalPages = docHtml.split('<div class="manual-page-break"></div>');

            logicalPages.forEach((pageHtml, logicalPageIndex) => {
                if (pageHtml.trim() === "") return;

                const pageDiv = document.createElement('div');
                pageDiv.className = 'page';

                const pageNumberDiv = document.createElement('div');
                pageNumberDiv.className = 'page-number';
                pageNumberDiv.textContent = `Página ${pageCounter}`;

                const contentDiv = document.createElement('div');
                contentDiv.className = 'page-content';

                let processedHtml = processPlaceholders(pageHtml);

                processedHtml = processedHtml.replace(/\t/g, '&emsp;&emsp;');
                processedHtml = processedHtml.replace(/<p>(<br\s*\/?>|\s|&nbsp;)*<\/p>/gi, '');
                processedHtml = processedHtml.replace(/<p>(<br\s*\/?>\s*)+/gi, '<p>');
                processedHtml = processedHtml.replace(/(<br\s*\/?>\s*)+<\/p>/gi, '</p>');
                processedHtml = processedHtml.replace(/(<br\s*\/?>\s*){2,}/gi, '<br>');
                processedHtml = processedHtml.replace(/\s{2,}/g, ' ');
                processedHtml = processedHtml.replace(/(&nbsp;){2,}/g, '&nbsp;');

                contentDiv.innerHTML = processedHtml;

                pageDiv.appendChild(contentDiv);
                pageDiv.appendChild(pageNumberDiv);
                pageContainer.appendChild(pageDiv);

                pageCounter++;
            });
        });

        if (isFinalized) {
            const inputs = pageContainer.querySelectorAll('input.editable-date, textarea.editable-text');
            inputs.forEach(input => {
                input.disabled = true;
                input.style.backgroundColor = '#f0f0f0';
                input.style.border = 'none';
                input.style.color = '#555';
            });
        }

        const signatureButtons = pageContainer.querySelectorAll('.open-signature-modal');
        const signatureImages = pageContainer.querySelectorAll('.signature-image-embedded');

        const totalSignatures = signatureButtons.length + signatureImages.length;
        const completedSignatures = signatureImages.length;

        const signatureCounter = document.getElementById('signature-counter');
        if (signatureCounter) {
            signatureCounter.textContent = `${completedSignatures}/${totalSignatures}`;
        }

        pendingSignatureElements = Array.from(signatureButtons);
        const sigNavButton = document.getElementById('signature-nav-button');

        if (pendingSignatureElements.length > 0) {
            sigNavButton.style.display = 'flex';
        } else {
            sigNavButton.style.display = 'none';
        }
    }

    const sigNavButton = document.getElementById('signature-nav-button');
    if (sigNavButton) {
        sigNavButton.addEventListener('click', () => {
            if (pendingSignatureElements.length === 0) return;

            currentSignatureIndex++;
            if (currentSignatureIndex >= pendingSignatureElements.length) {
                currentSignatureIndex = 0;
            }

            const nextSignature = pendingSignatureElements[currentSignatureIndex];
            nextSignature.scrollIntoView({ behavior: 'smooth', block: 'center' });

            nextSignature.classList.add('signature-focus');
            setTimeout(() => nextSignature.classList.remove('signature-focus'), 1600);
        });
    }

    document.body.addEventListener('click', function(e) {
        if (isFinalized && e.target.closest('.excluir-anexo-btn')) {
            alert("Não é possível excluir anexos de um processo finalizado.");
            return;
        }

        const target = e.target.closest('.excluir-anexo-btn');
        if (target) {
            const anexoId = target.dataset.anexoId;
            if (confirm('Tem a certeza de que deseja excluir este anexo?')) {
                const url = `/Ouvidoria/anexo/${anexoId}/excluir/`;
                fetch(url, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': csrfToken }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        anexosDefesa = anexosDefesa.filter(a => a.id != anexoId);
                        anexosReconsideracao = anexosReconsideracao.filter(a => a.id != anexoId);
                        anexosReconsideracaoOficial = anexosReconsideracaoOficial.filter(a => a.id != anexoId);
                        renderAnexosGeral();
                        renderVisualizador();
                    } else {
                        alert('Erro ao excluir anexo: ' + data.message);
                    }
                })
                .catch(error => console.error('Erro:', error));
            }
        }
    });

    document.body.addEventListener('click', function(e) {
        const removeBtn = e.target.closest('.remove-signature-btn');
        if (removeBtn) {
            e.preventDefault();

            if (isFinalized) {
                alert("Não é possível remover assinaturas de um processo finalizado.");
                return;
            }

            if (!confirm('Tem certeza que deseja remover esta assinatura?')) {
                return;
            }

            const signatureType = removeBtn.dataset.signatureType;
            const signatureIndex = removeBtn.dataset.signatureIndex;
            const url = PATD_CONFIG.urls.removerAssinatura;
            const body = {
                signature_type: signatureType,
            };
            if (signatureIndex !== undefined) {
                body.signature_index = parseInt(signatureIndex, 10);
            }

            fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify(body)
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    window.location.reload();
                } else {
                    alert('Erro ao remover assinatura: ' + data.message);
                }
            })
            .catch(error => {
                console.error('Erro:', error);
                alert('Ocorreu um erro de comunicação.');
            });
        }
    });

    const btnJustificarPatd = document.getElementById('btn-justificar-patd');
    const justificarModal = document.getElementById('justificar-patd-modal');

    if (btnJustificarPatd && justificarModal) {
        const justificarForm = document.getElementById('justificar-patd-form');
        const cancelJustificarBtn = document.getElementById('cancel-justificar-btn');

        btnJustificarPatd.addEventListener('click', function() {
            justificarModal.classList.add('active');
        });

        if (cancelJustificarBtn) {
            cancelJustificarBtn.addEventListener('click', function() {
                justificarModal.classList.remove('active');
            });
        }

        justificarModal.addEventListener('click', (e) => {
            if (e.target === justificarModal) justificarModal.classList.remove('active');
        });

        if (justificarForm) {
            justificarForm.addEventListener('submit', function(e) {
                e.preventDefault();

                const motivo = document.getElementById('motivo-justificativa').value;
                const submitBtn = justificarForm.querySelector('button[type="submit"]');

                submitBtn.disabled = true;
                submitBtn.textContent = 'Processando...';

                const url = PATD_CONFIG.urls.justificarPatd;

                fetch(url, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    },
                    body: JSON.stringify({ 'motivo_justificativa': motivo })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        alert(data.message);
                        window.location.reload();
                    } else {
                        alert('Erro ao justificar: ' + data.message);
                        submitBtn.disabled = false;
                        submitBtn.textContent = 'Confirmar Justificativa';
                    }
                })
                .catch(error => {
                    console.error('Erro:', error);
                    alert('Erro de comunicação ao justificar a transgressão.');
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Confirmar Justificativa';
                });
            });
        }
    }

    const finalizarModal = document.getElementById('finalizar-publicacao-modal');
    if (finalizarModal) {
        const openBtn = document.getElementById('btn-finalizar-modal');
        const cancelBtn = document.getElementById('cancel-finalizar-btn');

        if(openBtn) {
            openBtn.addEventListener('click', () => finalizarModal.classList.add('active'));
        }
        if(cancelBtn) {
            cancelBtn.addEventListener('click', () => finalizarModal.classList.remove('active'));
        }
        finalizarModal.addEventListener('click', e => {
            if (e.target === finalizarModal) finalizarModal.classList.remove('active');
        });
    }

    const patdStatus = PATD_CONFIG.patdStatus;
    const isOficialResponsavel = PATD_CONFIG.isOficialResponsavel;

    if (patdStatus === 'aguardando_nova_punicao' && isOficialResponsavel) {
        const analiseCard = document.getElementById('analise-disciplinar-card');
        const resumoCard = document.getElementById('resumo-analise-card');
        if (analiseCard) {
            analiseCard.style.display = 'none';
        }
        if (resumoCard) {
            resumoCard.style.display = 'block';
        }
    }

    const novaPunicaoModal = document.getElementById('nova-punicao-modal');
    if (novaPunicaoModal) {
        const openBtn = document.getElementById('btn-nova-punicao-modal');
        const cancelBtn = document.getElementById('cancel-nova-punicao-btn');
        const form = document.getElementById('form-nova-punicao');

        if(openBtn) {
            openBtn.addEventListener('click', () => novaPunicaoModal.classList.add('active'));
        }
        if(cancelBtn) {
            cancelBtn.addEventListener('click', () => novaPunicaoModal.classList.remove('active'));
        }
        if(form) {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                const dias = document.getElementById('nova-punicao-dias-input').value;
                const tipo = document.getElementById('nova-punicao-tipo-input').value;

                const url = PATD_CONFIG.urls.salvarNovaPunicao;
                fetch(url, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    },
                    body: JSON.stringify({ dias: dias, tipo: tipo })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        alert(data.message);
                        window.location.reload();
                    } else {
                        alert('Erro: ' + data.message);
                    }
                })
                .catch(error => console.error('Erro:', error));
            });
        }
    }

    function renderAnexosGeral() {
        const anexosCard = document.getElementById('anexos-card-geral');
        const defesaContainer = document.getElementById('anexos-defesa-container-geral');
        const defesaList = document.getElementById('anexos-defesa-list-geral');
        const reconsideracaoContainer = document.getElementById('anexos-reconsideracao-container-geral');
        const reconsideracaoList = document.getElementById('anexos-reconsideracao-list-geral');
        const reconsideracaoOficialContainer = document.getElementById('anexos-reconsideracao-oficial-container-geral');
        const reconsideracaoOficialList = document.getElementById('anexos-reconsideracao-oficial-list-geral');

        defesaList.innerHTML = '';
        reconsideracaoList.innerHTML = '';
        reconsideracaoOficialList.innerHTML = '';

        let hasAnexos = false;

        if (anexosDefesa.length > 0) {
            defesaContainer.style.display = 'block';
            anexosDefesa.forEach(anexo => {
                const li = document.createElement('li');
                li.innerHTML = `
                    <span>${anexo.nome}</span>
                    <div class="anexo-actions">
                        <a href="${anexo.url}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-secondary">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" style="width:16px; height:16px;"><path stroke-linecap="round" stroke-linejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" /></svg>
                            Abrir
                        </a>
                        ${!isFinalized ? `<button class="btn btn-sm btn-delete excluir-anexo-btn" data-anexo-id="${anexo.id}">Excluir</button>` : ''}
                    </div>
                `;
                defesaList.appendChild(li);
            });
            hasAnexos = true;
        } else {
            defesaContainer.style.display = 'none';
        }

        if (anexosReconsideracao.length > 0) {
            reconsideracaoContainer.style.display = 'block';
            anexosReconsideracao.forEach(anexo => {
                const li = document.createElement('li');
                li.innerHTML = `
                    <span>${anexo.nome}</span>
                    <div class="anexo-actions">
                        <a href="${anexo.url}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-secondary">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" style="width:16px; height:16px;"><path stroke-linecap="round" stroke-linejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" /></svg>
                            Abrir
                        </a>
                        ${!isFinalized ? `<button class="btn btn-sm btn-delete excluir-anexo-btn" data-anexo-id="${anexo.id}">Excluir</button>` : ''}
                    </div>
                `;
                reconsideracaoList.appendChild(li);
            });
            hasAnexos = true;
        } else {
            reconsideracaoContainer.style.display = 'none';
        }

        if (anexosReconsideracaoOficial.length > 0) {
            reconsideracaoOficialContainer.style.display = 'block';
            anexosReconsideracaoOficial.forEach(anexo => {
                const li = document.createElement('li');
                li.innerHTML = `
                    <span>${anexo.nome}</span>
                    <div class="anexo-actions">
                        <a href="${anexo.url}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-secondary">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" style="width:16px; height:16px;"><path stroke-linecap="round" stroke-linejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" /></svg>
                            Abrir
                        </a>
                        ${!isFinalized ? `<button class="btn btn-sm btn-delete excluir-anexo-btn" data-anexo-id="${anexo.id}">Excluir</button>` : ''}
                    </div>
                `;
                reconsideracaoOficialList.appendChild(li);
            });
            hasAnexos = true;
        } else {
            reconsideracaoOficialContainer.style.display = 'none';
        }

        anexosCard.style.display = hasAnexos ? 'block' : 'none';
    }

    const btnApurar = document.getElementById('btn-apurar');
    const apuracaoForm = document.getElementById('apuracao-form');
    const btnSalvarApuracao = document.getElementById('btn-salvar-apuracao');
    const btnReanalisar = document.getElementById('btn-reanalisar-apuracao');
    const btnCancelarApuracao = document.getElementById('btn-cancelar-apuracao');

    const punicaoDiasInput = document.getElementById('id_punicao_dias');
    const punicaoTipoSelect = document.getElementById('id_punicao_tipo');

    if (punicaoTipoSelect && punicaoDiasInput) {
        punicaoTipoSelect.addEventListener('change', () => {
            const selectedType = punicaoTipoSelect.value;
            if (selectedType === 'repreensão por escrito' || selectedType === 'repreensão verbal') {
                punicaoDiasInput.value = 0;
                punicaoDiasInput.disabled = true;
            } else {
                punicaoDiasInput.disabled = false;
            }
        });
    }

    function preencherFormApuracao(data) {
        if (!data) {
            console.warn("Nenhum dado de análise recebido para preencher o formulário.");
            return;
        }

        const itensTextarea = document.getElementById('itens_enquadrados');
        if (data.itens && Array.isArray(data.itens)) {
            itensTextarea.value = data.itens.map(item => `${item.numero}: ${item.descricao}`).join('\n');
        } else {
            itensTextarea.value = "Não foi possível extrair os itens.";
        }

        const atenuantesInput = document.getElementById('atenuantes');
        const agravantesInput = document.getElementById('agravantes');
        if (data.circunstancias) {
            atenuantesInput.value = data.circunstancias.atenuantes ? data.circunstancias.atenuantes.join(', ') : "Nenhuma";
            agravantesInput.value = data.circunstancias.agravantes ? data.circunstancias.agravantes.join(', ') : "Nenhuma";
        } else {
            atenuantesInput.value = "Erro na análise";
            agravantesInput.value = "Erro na análise";
        }

        const punicaoString = data.punicao || "";
        document.getElementById('punicao_sugerida_original_llm').value = punicaoString;

        const punicaoDiasInputJS = document.getElementById('id_punicao_dias');
        const punicaoTipoSelectJS = document.getElementById('id_punicao_tipo');

        const match = punicaoString.match(/(\d+)\s+dias\s+de\s+(.+)/i);
        if (match) {
            const dias = parseInt(match[1], 10);
            let tipo = match[2].toLowerCase().trim();

            if (tipo === "repreensão") {
                tipo = "repreensão por escrito";
            }

            punicaoDiasInputJS.value = dias;
            if ([...punicaoTipoSelectJS.options].some(opt => opt.value === tipo)) {
                punicaoTipoSelectJS.value = tipo;
            } else {
                punicaoTipoSelectJS.value = '';
            }

        } else if (punicaoString.toLowerCase().includes('repreensão')) {
            punicaoDiasInputJS.value = 0;
            if (punicaoString.toLowerCase().includes('verbal')) {
                punicaoTipoSelectJS.value = 'repreensão verbal';
            } else {
                punicaoTipoSelectJS.value = 'repreensão por escrito';
            }
        } else if (punicaoString) {
            punicaoDiasInputJS.value = 0;
            punicaoTipoSelectJS.value = '';
        }

        if (punicaoTipoSelectJS) {
            punicaoTipoSelectJS.dispatchEvent(new Event('change'));
        }

        if(apuracaoForm) apuracaoForm.style.display = 'block';
        if(btnApurar) btnApurar.style.display = 'none';
    }

    function fetchAnalisePunicao(forceReanalyze = false) {
        if(btnApurar) btnApurar.classList.add('loading');
        if(btnReanalisar) btnReanalisar.classList.add('loading');

        const url = PATD_CONFIG.urls.analisarPunicao;

        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ force_reanalyze: forceReanalyze })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success' && data.analise_data) {
                preencherFormApuracao(data.analise_data);
            } else {
                alert('Erro ao buscar análise: ' + (data.message || 'Erro desconhecido.'));
                if (analiseData && !forceReanalyze) {
                    preencherFormApuracao(analiseData);
                }
            }
        })
        .catch(error => {
            console.error('Erro no fetch da análise:', error);
            alert('Erro de comunicação ao buscar análise da punição.');
        })
        .finally(() => {
            if(btnApurar) btnApurar.classList.remove('loading');
            if(btnReanalisar) btnReanalisar.classList.remove('loading');
        });
    }

    if (btnApurar) {
        btnApurar.addEventListener('click', () => {
            if (analiseData) {
                preencherFormApuracao(analiseData);
            } else {
                fetchAnalisePunicao(false);
            }
        });
    }

    if (btnReanalisar) {
        btnReanalisar.addEventListener('click', () => {
            if (confirm('Tem certeza que deseja re-analisar? Isso pode sobrescrever os dados atuais.')) {
                fetchAnalisePunicao(true);
            }
        });
    }

    if (btnCancelarApuracao) {
        btnCancelarApuracao.addEventListener('click', () => {
            if(apuracaoForm) apuracaoForm.style.display = 'none';
            if(btnApurar) btnApurar.style.display = 'inline-flex';
        });
    }

    if (btnSalvarApuracao) {
        btnSalvarApuracao.addEventListener('click', () => {
            const btnSpinner = btnSalvarApuracao.querySelector('.spinner');

            const punicaoDias = document.getElementById('id_punicao_dias').value;
            const punicaoTipo = document.getElementById('id_punicao_tipo').value;

            if (!punicaoTipo) {
                alert('Por favor, selecione um tipo de punição.');
                return;
            }

            if(btnSpinner) btnSpinner.style.display = 'inline-block';
            btnSalvarApuracao.disabled = true;

            let punicaoSugeridaString = "";
            if (punicaoTipo === 'repreensão por escrito' || punicaoTipo === 'repreensão verbal') {
                punicaoSugeridaString = punicaoTipo;
            } else {
                punicaoSugeridaString = `${punicaoDias} dias de ${punicaoTipo}`;
            }

            const data = {
                itens_enquadrados: document.getElementById('itens_enquadrados').value.split('\n')
                                                    .filter(line => line.trim() !== "")
                                                    .map(line => {
                                                        const parts = line.split(':');
                                                        return { numero: parts[0] ? parts[0].trim() : 'N/A', descricao: parts[1] ? parts[1].trim() : line };
                                                    }),
                circunstancias: {
                    atenuantes: document.getElementById('atenuantes').value.split(',').map(s => s.trim()).filter(s => s && s !== "Nenhuma"),
                    agravantes: document.getElementById('agravantes').value.split(',').map(s => s.trim()).filter(s => s && s !== "Nenhuma")
                },
                punicao_sugerida: punicaoSugeridaString,
                punicao_dias: parseInt(punicaoDias, 10),
                punicao_tipo: punicaoTipo
            };

            const url = PATD_CONFIG.urls.salvarApuracao;
            fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify(data)
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    alert('Apuração salva com sucesso! A página será recarregada.');
                    window.location.reload();
                } else {
                    alert('Erro ao salvar apuração: ' + data.message);
                    if(btnSpinner) btnSpinner.style.display = 'none';
                    btnSalvarApuracao.disabled = false;
                }
            })
            .catch(error => {
                console.error('Erro ao salvar apuração:', error);
                alert('Erro de comunicação ao salvar a apuração.');
                if(btnSpinner) btnSpinner.style.display = 'none';
                btnSalvarApuracao.disabled = false;
            });
        });
    }

    renderAnexosGeral();

    const activeTabId = localStorage.getItem(`activePatdTab-${PATD_CONFIG.patdPk}`) || 'tab-detalhes';
    document.querySelectorAll('.tab-link').forEach(l => l.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));

    const activeLink = document.querySelector(`.tab-link[data-target="${activeTabId}"]`);
    const activePanel = document.getElementById(activeTabId);

    if (activeLink) {
        activeLink.classList.add('active');
    } else {
        document.querySelector('.tab-link[data-target="tab-detalhes"]').classList.add('active');
    }

    if (activePanel) {
        activePanel.classList.add('active');
    } else {
        document.getElementById('tab-detalhes').classList.add('active');
    }

    if (activeTabId === 'tab-visualizador' && activePanel) {
        renderVisualizador();
    } else if (!activePanel && activeTabId === 'tab-visualizador') {
        renderVisualizador();
    }

    const aprovarModal = document.getElementById('aprovar-patd-modal');
    const aprovarForm = document.getElementById('aprovar-patd-form');
    const aprovarModalTitle = document.getElementById('aprovar-modal-title');
    const cancelAprovarBtn = document.getElementById('cancel-aprovar-btn');

    document.body.addEventListener('click', function(e) {
        if (e.target.classList.contains('open-aprovar-modal-btn')) {
            const patdPk = e.target.dataset.patdPk;
            const patdNumero = e.target.dataset.patdNumero;
            const url = `/Ouvidoria/patd/${patdPk}/aprovar/`;
            aprovarForm.action = url;
            aprovarModalTitle.textContent = `Aprovar PATD Nº ${patdNumero}`;
            aprovarModal.classList.add('active');
        }
    });

    if (cancelAprovarBtn) {
        cancelAprovarBtn.addEventListener('click', () => {
            aprovarModal.classList.remove('active');
        });
    }

    if (aprovarModal) {
        aprovarModal.addEventListener('click', (e) => {
            if (e.target === aprovarModal) {
                aprovarModal.classList.remove('active');
            }
        });
    }
});

document.querySelectorAll('.file-input-check').forEach(input => {
    input.addEventListener('change', function() {
        const maxSize = 10 * 1024 * 1024;
        if (this.files && this.files[0]) {
            if (this.files[0].size > maxSize) {
                alert("O arquivo selecionado é muito grande (Máximo 10MB). Por favor, reduza o tamanho do arquivo ou escolha outro.");
                this.value = '';
            }
        }
    });
});
