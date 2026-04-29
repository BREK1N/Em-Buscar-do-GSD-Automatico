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
const testemunha1SigData  = PATD_CONFIG.hasTestemunha1Sig ? PATD_CONFIG.testemunha1SigUrl : '';
const testemunha2SigData  = PATD_CONFIG.hasTestemunha2Sig ? PATD_CONFIG.testemunha2SigUrl : '';
const oficialSigData      = PATD_CONFIG.oficialSigUrl;
const comandanteSigData   = PATD_CONFIG.comandanteSigUrl;

let anexosDefesa                 = PATD_CONFIG.anexosDefesa;
const formularioResumo           = PATD_CONFIG.formularioResumo;
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
            const ratio = Math.max(window.devicePixelRatio || 1, 2);
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
            const signatureData = signaturePad.toDataURL('image/png');

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
        const addDefesaBtn       = document.getElementById('add-defesa-btn');
        const confirmDefesaModal = document.getElementById('confirm-defesa-modal');
        const submitDefesaBtn    = document.getElementById('submit-defesa-btn');
        const cancelConfirmBtn   = document.getElementById('cancel-confirm-defesa-btn');
        const finalSubmitBtn     = document.getElementById('final-submit-defesa-btn');
        const formDefesa         = document.getElementById('form-alegacao-defesa');
        const filePicker         = document.getElementById('defesa-file-picker');
        const anexosList         = document.getElementById('defesa-anexos-list');
        const addAnexoBtn        = document.getElementById('defesa-add-anexo-btn');

        // Lista de arquivos selecionados pelo usuário
        let selectedFiles = [];

        function closeDefesaModal() { defesaModal.classList.remove('active'); }
        function openDefesaModal()  { defesaModal.classList.add('active'); }

        function renderAnexosList() {
            if (!anexosList) return;
            anexosList.innerHTML = '';
            selectedFiles.forEach((file, idx) => {
                const row = document.createElement('div');
                row.style.cssText = 'display:flex;align-items:center;gap:8px;padding:8px 12px;background:var(--sidebar-bg);border:1px solid var(--border-color);border-radius:8px;font-size:.88rem;';
                const icon = document.createElement('span');
                icon.textContent = file.type.startsWith('image/') ? '🖼️' : '📄';
                const name = document.createElement('span');
                name.style.cssText = 'flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text-primary);';
                name.textContent = file.name;
                const size = document.createElement('span');
                size.style.cssText = 'color:var(--text-secondary);font-size:.8rem;flex-shrink:0;';
                size.textContent = (file.size / 1024).toFixed(0) + ' KB';
                const removeBtn = document.createElement('button');
                removeBtn.type = 'button';
                removeBtn.style.cssText = 'background:none;border:none;cursor:pointer;color:var(--danger-color);font-size:1rem;padding:0;line-height:1;flex-shrink:0;';
                removeBtn.title = 'Remover';
                removeBtn.textContent = '✕';
                removeBtn.addEventListener('click', () => {
                    selectedFiles.splice(idx, 1);
                    renderAnexosList();
                });
                row.append(icon, name, size, removeBtn);
                anexosList.appendChild(row);
            });
        }

        if (addAnexoBtn && filePicker) {
            addAnexoBtn.addEventListener('click', () => {
                filePicker.value = '';
                filePicker.click();
            });
            filePicker.addEventListener('change', () => {
                Array.from(filePicker.files).forEach(f => selectedFiles.push(f));
                renderAnexosList();
            });
        }

        if (addDefesaBtn) addDefesaBtn.addEventListener('click', openDefesaModal);
        document.body.addEventListener('click', e => {
            if (e.target && e.target.id === 'add-defesa-btn-doc') openDefesaModal();
        });

        document.querySelectorAll('#cancel-defesa-btn, #cancel-defesa-btn-2').forEach(btn => {
            btn.addEventListener('click', closeDefesaModal);
        });

        if (submitDefesaBtn) submitDefesaBtn.addEventListener('click', () => {
            const alegacaoText = document.getElementById('alegacao-defesa-texto').value;
            if (alegacaoText.trim() === '' && selectedFiles.length === 0) {
                alert('É necessário fornecer um texto ou anexar pelo menos um ficheiro.');
                return;
            }
            closeDefesaModal();
            if (confirmDefesaModal) confirmDefesaModal.classList.add('active');
        });

        if (cancelConfirmBtn) cancelConfirmBtn.addEventListener('click', () => {
            confirmDefesaModal.classList.remove('active');
            defesaModal.classList.add('active');
        });

        if (finalSubmitBtn) finalSubmitBtn.addEventListener('click', () => {
            const formData = new FormData();
            const alegacaoTextarea = document.getElementById('alegacao-defesa-texto');
            if (alegacaoTextarea) formData.append('alegacao_defesa', alegacaoTextarea.value);
            selectedFiles.forEach(f => formData.append('anexos_defesa', f));
            const url = PATD_CONFIG.urls.salvarAlegacaoDefesa;
            finalSubmitBtn.disabled = true;
            finalSubmitBtn.textContent = 'Enviando...';
            fetch(url, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrfToken },
                body: formData
            })
            .then(r => r.json())
            .then(data => {
                if (data.status === 'success') window.location.reload();
                else { alert('Erro: ' + data.message); finalSubmitBtn.disabled = false; finalSubmitBtn.textContent = 'Sim, Enviar'; }
            })
            .catch(() => { alert('Erro de conexão.'); finalSubmitBtn.disabled = false; finalSubmitBtn.textContent = 'Sim, Enviar'; });
        });
    }

    const extenderPrazoModal = document.getElementById('extender-prazo-modal');
    const extenderPrazoBtn = document.getElementById('extender-prazo-btn');
    const prosseguirBtn = document.getElementById('prosseguir-sem-defesa-btn');
    function handleProsseguirSemAlegacao() {
        // Verifica se as testemunhas estão atribuídas
        const faltando = [];
        if (!PATD_CONFIG.temTestemunha1) faltando.push('1ª Testemunha');
        if (!PATD_CONFIG.temTestemunha2) faltando.push('2ª Testemunha');
        if (faltando.length > 0) {
            const msg = `⚠️ Não é possível prosseguir sem alegação.\n\nAs seguintes testemunhas ainda não foram atribuídas:\n• ${faltando.join('\n• ')}\n\nAtribua as testemunhas na aba "Editar" da PATD antes de continuar.`;
            alert(msg);
            return;
        }
        if (confirm('Tem certeza que deseja prosseguir sem a alegação de defesa? Esta ação registrará a preclusão e não poderá ser desfeita.')) {
            const url = PATD_CONFIG.urls.prosseguirSemAlegacao;
            fetch(url, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrfToken }
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') window.location.reload();
                else if (data.code === 'testemunhas_ausentes') alert('⚠️ ' + data.message);
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

        // prazo_override tem prioridade sobre o cálculo por dias úteis
        let deadline;
        if (PATD_CONFIG.prazoOverrideIso && PATD_CONFIG.prazoOverrideIso !== 'None') {
            deadline = new Date(PATD_CONFIG.prazoOverrideIso);
        } else {
            let deadlineDate = addBusinessDays(dataCiencia, prazoDias);
            deadline = new Date(deadlineDate.getFullYear(), deadlineDate.getMonth(), deadlineDate.getDate() + 1);
        }

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
                }
            }
            localStorage.setItem(`activePatdTab-${PATD_CONFIG.patdPk}`, link.dataset.target);
        });
    });

    function generateEmbeddedAnexoHTML(anexo) {
        const fileType = (anexo.tipo_arquivo || '').toLowerCase();
        const imageTypes = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'];
        const isImage = imageTypes.includes(fileType);
        const isPdf = fileType === 'pdf';

        if (isImage) {
            return `<img src="${anexo.url}" alt="${anexo.nome}" style="width:100%; height:auto; display:block;" />`;
        } else if (isPdf) {
            return `<iframe src="${anexo.url}" style="width:100%; height:100%; min-height:600px; border:none; display:block;" title="${anexo.nome}"></iframe>`;
        } else {
            return `
                <p>Clique abaixo para abrir o anexo.</p>
                <a href="${anexo.url}" class="btn-download" target="_blank" rel="noopener noreferrer">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" style="width:16px;height:16px;"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" /></svg>
                    Abrir/Baixar Anexo (.${fileType})
                </a>`;
        }
    }

    // Retorna um array de HTMLs — um por folha — incluindo uma folha por página de PDFs
    function generateAnexosPages(anexos) {
        if (!anexos || anexos.length === 0) return [];
        const result = [];
        for (const anexo of anexos) {
            if (anexo.pages && Array.isArray(anexo.pages) && anexo.pages.length > 0) {
                // PDF pré-renderizado: cada página vira uma folha separada
                for (const pageDataUrl of anexo.pages) {
                    result.push(`<img src="${pageDataUrl}" style="width:100%;height:auto;display:block;" />`);
                }
            } else {
                result.push(generateEmbeddedAnexoHTML(anexo));
            }
        }
        return result;
    }

    function processPlaceholders(text) {
        let processedHtml = text;
        if (processedHtml.includes('{Assinatura_Imagem_Testemunha_1}') || processedHtml.includes('{Botao Assinar Testemunha 1}') ||
            processedHtml.includes('{Assinatura_Imagem_Testemunha_2}') || processedHtml.includes('{Botao Assinar Testemunha 2}')) {
            console.log('[Assinatura Debug] hasTestemunha1Sig:', PATD_CONFIG.hasTestemunha1Sig, '| URL:', testemunha1SigData || '(vazio)');
            console.log('[Assinatura Debug] hasTestemunha2Sig:', PATD_CONFIG.hasTestemunha2Sig, '| URL:', testemunha2SigData || '(vazio)');
            console.log('[Assinatura Debug] placeholder T1 no doc:', processedHtml.includes('{Assinatura_Imagem_Testemunha_1}') ? 'Imagem' : (processedHtml.includes('{Botao Assinar Testemunha 1}') ? 'Botao' : 'ausente'));
            console.log('[Assinatura Debug] placeholder T2 no doc:', processedHtml.includes('{Assinatura_Imagem_Testemunha_2}') ? 'Imagem' : (processedHtml.includes('{Botao Assinar Testemunha 2}') ? 'Botao' : 'ausente'));
        }

        processedHtml = processedHtml.replace(/{Botao Adicionar Alegacao}/g, `<button id="add-defesa-btn-doc" class="btn btn-sm btn-primary">Adicionar Alegação de Defesa</button>`);
        processedHtml = processedHtml.replace(/{Botao Adicionar Reconsideracao}/g, `<button id="add-reconsideracao-texto-btn-doc" class="btn btn-sm btn-primary">Adicionar Texto de Reconsideração</button>`);

        // Anexos são renderizados como folhas individuais no loop principal — não substituir inline
        processedHtml = processedHtml.replace(/{ANEXOS_DEFESA_PLACEHOLDER}/g, '');
        processedHtml = processedHtml.replace(/{ANEXOS_RECONSIDERACAO_PLACEHOLDER}/g, '');
        processedHtml = processedHtml.replace(/{ANEXO_OFICIAL_RECONSIDERACAO_PLACEHOLDER}/g, '');
        processedHtml = processedHtml.replace(/{FORMULARIO_RESUMO_PLACEHOLDER}/g, '');

        processedHtml = processedHtml.replace(/{Assinatura Alegacao Defesa}/g, hasDefesaSig ? createSignatureHtml(defesaSigData, 'Assinatura da Defesa', 'defesa') : `<button class="btn btn-sm btn-primary open-signature-modal" data-type="defesa">Assinar Alegação de Defesa</button>`);
        processedHtml = processedHtml.replace(/{Assinatura Reconsideracao}/g, hasReconSig ? createSignatureHtml(reconSigData, 'Assinatura da Reconsideração', 'reconsideracao') : `<button class="btn btn-sm btn-primary open-signature-modal" data-type="reconsideracao">Assinar Reconsideração</button>`);

        processedHtml = processedHtml.replace(/{Assinatura_Imagem_Oficial_Apurador}/g, oficialSigData ? createSignatureHtml(oficialSigData, 'Assinatura do Oficial Apurador', 'oficial') : '[Sem assinatura]');
        processedHtml = processedHtml.replace(/{Assinatura_Imagem_Comandante_GSD}/g, comandanteSigData ? `<img class="signature-image-embedded" src="${comandanteSigData}" alt="Assinatura do Comandante">` : '[Sem assinatura]');
        processedHtml = processedHtml.replace(/{Assinatura_Imagem_Testemunha_1}/g, testemunha1SigData ? createSignatureHtml(testemunha1SigData, 'Assinatura da Testemunha 1', 'testemunha1') : '[Sem assinatura]');
        processedHtml = processedHtml.replace(/{Assinatura_Imagem_Testemunha_2}/g, testemunha2SigData ? createSignatureHtml(testemunha2SigData, 'Assinatura da Testemunha 2', 'testemunha2') : '[Sem assinatura]');

        processedHtml = processedHtml.replace(/{Assinatura Militar Arrolado}/g, () => {
            const index = signatureIndex++;
            console.log(`[Mil Debug] {Assinatura Militar Arrolado} index=${index}, url=${assinaturasMilitar[index] || '(vazio)'}`);
            if (assinaturasMilitar[index]) {
                return createSignatureHtml(assinaturasMilitar[index], `Assinatura ${index + 1}`, 'ciencia', index);
            } else {
                return `<button class="btn btn-sm btn-primary open-signature-modal" data-type="ciencia" data-index="${index}">Assinar</button>`;
            }
        });

        processedHtml = processedHtml.replace(/{Botao Assinar Oficial}/g, oficialSigData
            ? createSignatureHtml(oficialSigData, 'Assinatura do Oficial Apurador', 'oficial')
            : `<button class="btn btn-sm btn-primary open-signature-modal" data-type="oficial">Assinar</button>`);
        processedHtml = processedHtml.replace(/{Botao Assinar Testemunha 1}/g, testemunha1SigData
            ? createSignatureHtml(testemunha1SigData, 'Assinatura da Testemunha 1', 'testemunha1')
            : `<button class="btn btn-sm btn-primary open-signature-modal" data-type="testemunha" data-testemunha-num="1">Assinar (Testemunha 1)</button>`);
        processedHtml = processedHtml.replace(/{Botao Assinar Testemunha 2}/g, testemunha2SigData
            ? createSignatureHtml(testemunha2SigData, 'Assinatura da Testemunha 2', 'testemunha2')
            : `<button class="btn btn-sm btn-primary open-signature-modal" data-type="testemunha" data-testemunha-num="2">Assinar (Testemunha 2)</button>`);

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

    // ── Zoom ──
    let _zoom = 1.0;
    const ZOOM_STEP = 0.1;
    const ZOOM_MIN  = 0.4;
    const ZOOM_MAX  = 2.0;

    function _applyZoom(z) {
        _zoom = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, z));
        const wrapper = document.getElementById('doc-scale-wrapper');
        if (wrapper) {
            wrapper.style.transform = `scale(${_zoom})`;
            // Ajusta a altura do wrapper para não deixar espaço em branco
            wrapper.style.marginBottom = _zoom < 1
                ? `${(1 - _zoom) * -wrapper.scrollHeight * 0.5}px`
                : '0';
        }
        const lbl = document.getElementById('zoom-label');
        if (lbl) lbl.textContent = Math.round(_zoom * 100) + '%';
    }

    function _fitWidth() {
        const container = pageContainer;
        if (!container) return;
        const containerW = container.clientWidth - 40; // padding
        const pageW = 21 * 37.7953; // 21cm em px
        _applyZoom(containerW / pageW);
    }

    document.getElementById('zoom-in-btn')?.addEventListener('click',  () => _applyZoom(_zoom + ZOOM_STEP));
    document.getElementById('zoom-out-btn')?.addEventListener('click', () => _applyZoom(_zoom - ZOOM_STEP));
    document.getElementById('zoom-fit-btn')?.addEventListener('click', _fitWidth);

    // Zoom com Ctrl+scroll
    pageContainer?.addEventListener('wheel', e => {
        if (!e.ctrlKey) return;
        e.preventDefault();
        _applyZoom(_zoom + (e.deltaY < 0 ? ZOOM_STEP : -ZOOM_STEP));
    }, { passive: false });

    // ── Navegação de páginas ──
    let _pageEls = [];

    function _updatePageIndicator() {
        if (!_pageEls.length) return;
        const containerRect = pageContainer.getBoundingClientRect();
        let current = 0;
        _pageEls.forEach((p, i) => {
            const r = p.getBoundingClientRect();
            if (r.top <= containerRect.top + containerRect.height / 2) current = i;
        });
        const ind = document.getElementById('page-indicator');
        if (ind) ind.textContent = `${current + 1} / ${_pageEls.length}`;
    }

    pageContainer?.addEventListener('scroll', _updatePageIndicator);

    function _scrollToPage(idx) {
        if (!_pageEls[idx]) return;
        _pageEls[idx].scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    document.getElementById('prev-page-btn')?.addEventListener('click', () => {
        const containerRect = pageContainer.getBoundingClientRect();
        let current = 0;
        _pageEls.forEach((p, i) => {
            const r = p.getBoundingClientRect();
            if (r.top <= containerRect.top + 10) current = i;
        });
        _scrollToPage(Math.max(0, current - 1));
    });

    document.getElementById('next-page-btn')?.addEventListener('click', () => {
        const containerRect = pageContainer.getBoundingClientRect();
        let current = 0;
        _pageEls.forEach((p, i) => {
            const r = p.getBoundingClientRect();
            if (r.top <= containerRect.top + 10) current = i;
        });
        _scrollToPage(Math.min(_pageEls.length - 1, current + 1));
    });

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

        if (!documentPages || documentPages.length === 0) {
            pageContainer.innerHTML = '<p style="text-align:center;color:var(--text-secondary);padding:40px;">O conteúdo do documento está vazio.</p>';
            return;
        }

        // Wrapper que recebe transform de zoom
        const scaleWrapper = document.createElement('div');
        scaleWrapper.id = 'doc-scale-wrapper';
        pageContainer.appendChild(scaleWrapper);

        let pageCounter = 1;

        // Dimensões e fonte padrão (fallback) — sobrescritas pelo page-meta de cada doc
        let _curW = 21, _curH = 29.7, _curTop = 2.5, _curBot = 2.5, _curLeft = 2.5, _curRight = 2.5;
        let _curFont = 'Times New Roman', _curFontSize = 12;

        function buildPageDiv(html) {
            const pageDiv = document.createElement('div');
            pageDiv.className = 'page';
            pageDiv.dataset.pageNum = pageCounter;

            const contentDiv = document.createElement('div');
            contentDiv.className = 'page-content';

            let processedHtml = processPlaceholders(html);
            processedHtml = processedHtml.replace(/\t/g, '&emsp;&emsp;');
            processedHtml = processedHtml.replace(/<p>(<br\s*\/?>|\s|&nbsp;)*<\/p>/gi, '');
            processedHtml = processedHtml.replace(/<p>(<br\s*\/?>\s*)+/gi, '<p>');
            processedHtml = processedHtml.replace(/(<br\s*\/?>\s*)+<\/p>/gi, '</p>');
            contentDiv.innerHTML = processedHtml;

            // Lê dimensões reais do page-meta injetado pelo servidor
            const meta = contentDiv.querySelector('.page-meta');
            if (meta) {
                const d = meta.dataset;
                if (d.width)    _curW        = parseFloat(d.width);
                if (d.height)   _curH        = parseFloat(d.height);
                if (d.top)      _curTop      = parseFloat(d.top);
                if (d.bottom)   _curBot      = parseFloat(d.bottom);
                if (d.left)     _curLeft     = parseFloat(d.left);
                if (d.right)    _curRight    = parseFloat(d.right);
                if (d.font)     _curFont     = d.font;
                if (d.fontsize) _curFontSize = parseFloat(d.fontsize);
                meta.remove();
            }

            // Descarta seções sem conteúdo visível (ex: page-meta sozinho antes de {nova_pagina})
            const hasContent = contentDiv.textContent.trim() ||
                               contentDiv.querySelector('img, iframe, embed, input, button, canvas');
            if (!hasContent) return null;

            // Aplica dimensões, margens e fonte exatas do DOCX
            pageDiv.style.width         = `${_curW}cm`;
            pageDiv.style.minHeight     = `${_curH}cm`;
            pageDiv.style.paddingTop    = `${_curTop}cm`;
            pageDiv.style.paddingBottom = `${_curBot}cm`;
            pageDiv.style.paddingLeft   = `${_curLeft}cm`;
            pageDiv.style.paddingRight  = `${_curRight}cm`;
            pageDiv.style.fontFamily    = `'${_curFont}', serif`;
            pageDiv.style.fontSize      = `${_curFontSize}pt`;

            const numDiv = document.createElement('div');
            numDiv.className = 'page-number';
            numDiv.style.bottom = `${Math.min(_curBot * 0.4, 1)}cm`;
            numDiv.style.right  = `${_curRight}cm`;
            numDiv.textContent = `Página ${pageCounter++}`;

            pageDiv.appendChild(contentDiv);
            pageDiv.appendChild(numDiv);
            return pageDiv;
        }

        // Mapa de placeholders → array de páginas de anexo
        const anexoPlaceholders = {
            '{ANEXOS_DEFESA_PLACEHOLDER}':                generateAnexosPages(anexosDefesa),
            '{ANEXOS_RECONSIDERACAO_PLACEHOLDER}':        generateAnexosPages(anexosReconsideracao),
            '{ANEXO_OFICIAL_RECONSIDERACAO_PLACEHOLDER}': generateAnexosPages(anexosReconsideracaoOficial),
            '{FORMULARIO_RESUMO_PLACEHOLDER}':            formularioResumo ? generateAnexosPages([formularioResumo]) : [],
        };
        const PAGE_BREAK = '<div class="manual-page-break"></div>';

        // Filtra page-breaks que precedem imediatamente um placeholder com lista vazia
        const filteredPages = documentPages.filter((docHtml, idx) => {
            if (docHtml.trim() !== PAGE_BREAK) return true;
            const next = documentPages[idx + 1];
            if (!next) return false;
            const nextTrimmed = next.trim().replace(/<p>|<\/p>/g, '').trim();
            const nextKey = Object.keys(anexoPlaceholders).find(k => nextTrimmed === k);
            return !(nextKey && anexoPlaceholders[nextKey].length === 0);
        });

        filteredPages.forEach((docHtml) => {
            // Page-breaks isolados não viram páginas
            if (docHtml.trim() === PAGE_BREAK) return;

            // Verifica se este "documento" é inteiramente um placeholder de anexos
            const trimmed = docHtml.trim().replace(/<p>|<\/p>/g, '').trim();
            const matchedKey = Object.keys(anexoPlaceholders).find(k => trimmed === k);
            if (matchedKey) {
                anexoPlaceholders[matchedKey].forEach(pageHtml => {
                    const div = buildPageDiv(pageHtml);
                    if (div) scaleWrapper.appendChild(div);
                });
                return;
            }

            // Extrai o page-meta do documento inteiro (só aparece na 1ª seção)
            // e reinjeta em todas as seções para que buildPageDiv leia as dimensões corretas
            const metaMatch = docHtml.match(/<div class="page-meta"[\s\S]*?><\/div>/);
            const sections = docHtml.split('<div class="manual-page-break"></div>');
            sections.forEach((sectionHtml, idx) => {
                if (!sectionHtml.trim()) return;
                const html = (idx > 0 && metaMatch) ? metaMatch[0] + sectionHtml : sectionHtml;
                const div = buildPageDiv(html);
                if (div) scaleWrapper.appendChild(div);
            });
        });

        // Atualiza lista de páginas e indicador
        _pageEls = Array.from(scaleWrapper.querySelectorAll('.page'));
        _updatePageIndicator();
        _applyZoom(_zoom); // aplica zoom atual

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
        if (signatureCounter) signatureCounter.textContent = `${completedSignatures}/${totalSignatures}`;

        pendingSignatureElements = Array.from(signatureButtons);
        const sigGroup = document.getElementById('sig-toolbar-group');
        if (sigGroup) sigGroup.style.display = totalSignatures > 0 ? 'flex' : 'none';
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
        if (analiseCard) analiseCard.style.display = 'none';
        if (resumoCard) resumoCard.style.display = 'block';
    }

    // --- Card Nova Punição Pós-Reconsideração ---
    const npCard = document.getElementById('nova-punicao-card');
    if (npCard) {
        const npDias = document.getElementById('np-dias');
        const npTipo = document.getElementById('np-tipo');
        const npBtnPreview = document.getElementById('np-btn-preview');
        const npBtnSalvar = document.getElementById('np-btn-salvar');
        const npPreviewBox = document.getElementById('np-preview');
        const npPreviewNatureza = document.getElementById('np-preview-natureza');
        const npPreviewComportamento = document.getElementById('np-preview-comportamento');

        // Desabilita dias se repreensão
        npTipo.addEventListener('change', () => {
            if (npTipo.value === 'repreensão') {
                npDias.value = 0;
                npDias.disabled = true;
            } else {
                npDias.disabled = false;
            }
            // Limpa preview ao mudar tipo
            npPreviewBox.style.display = 'none';
            npBtnSalvar.disabled = true;
        });

        npBtnPreview.addEventListener('click', () => {
            const tipo = npTipo.value;
            if (!tipo) { alert('Selecione o tipo de punição.'); return; }

            const spinner = npBtnPreview.querySelector('.spinner');
            if (spinner) spinner.style.display = 'inline-block';
            npBtnPreview.disabled = true;

            fetch(PATD_CONFIG.urls.previewNovaPunicao, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({ dias: npDias.value, tipo: tipo })
            })
            .then(r => r.json())
            .then(data => {
                if (data.status === 'success') {
                    npPreviewNatureza.textContent = data.natureza;
                    npPreviewComportamento.textContent = data.comportamento;
                    npPreviewComportamento.style.color = data.comportamento === 'Mau comportamento'
                        ? 'var(--danger-color)' : 'var(--success-color)';
                    npPreviewBox.style.display = 'block';
                    npBtnSalvar.disabled = false;
                } else {
                    alert('Erro: ' + data.message);
                }
            })
            .catch(err => { console.error(err); alert('Erro de comunicação.'); })
            .finally(() => {
                if (spinner) spinner.style.display = 'none';
                npBtnPreview.disabled = false;
            });
        });

        npBtnSalvar.addEventListener('click', () => {
            const tipo = npTipo.value;
            if (!tipo) { alert('Selecione o tipo de punição.'); return; }
            if (!confirm('Confirmar nova punição? Esta ação avançará o processo para publicação.')) return;

            const spinner = npBtnSalvar.querySelector('.spinner');
            if (spinner) spinner.style.display = 'inline-block';
            npBtnSalvar.disabled = true;

            fetch(PATD_CONFIG.urls.salvarNovaPunicao, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({ dias: npDias.value, tipo: tipo })
            })
            .then(r => r.json())
            .then(data => {
                if (data.status === 'success') {
                    alert('Nova punição salva com sucesso!');
                    window.location.reload();
                } else {
                    alert('Erro: ' + data.message);
                    if (spinner) spinner.style.display = 'none';
                    npBtnSalvar.disabled = false;
                }
            })
            .catch(err => {
                console.error(err);
                alert('Erro de comunicação.');
                if (spinner) spinner.style.display = 'none';
                npBtnSalvar.disabled = false;
            });
        });
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
                        ${isSuperuser && !isFinalized ? `<button class="btn btn-sm btn-delete excluir-anexo-btn" data-anexo-id="${anexo.id}">Excluir</button>` : ''}
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
                    if (data.primeira_prisao) {
                        // Mostra modal de confirmação do destino
                        const modal = document.getElementById('primeira-prisao-modal');
                        if (modal) {
                            modal.classList.add('active');
                            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]') ?
                                document.querySelector('[name=csrfmiddlewaretoken]').value :
                                (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '';

                            const enviarDestino = function(cmdBase) {
                                modal.classList.remove('active');
                                fetch(PATD_CONFIG.urls.confirmarDestinoApuracao, {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                                    body: JSON.stringify({ cmd_base: cmdBase })
                                })
                                .then(r => r.json())
                                .then(d => {
                                    if (d.status === 'success') window.location.reload();
                                    else alert('Erro ao confirmar destino: ' + d.message);
                                })
                                .catch(() => alert('Erro de comunicação ao confirmar destino.'));
                            };

                            document.getElementById('btn-confirmar-cmd-base').onclick = () => enviarDestino(true);
                            document.getElementById('btn-confirmar-fluxo-normal').onclick = () => enviarDestino(false);
                        } else {
                            window.location.reload();
                        }
                    } else {
                        alert('Apuração salva com sucesso! A página será recarregada.');
                        window.location.reload();
                    }
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

    // Modal – Despacho de Abertura (CMD GSD)
    const despachoModal = document.getElementById('despacho-abertura-modal');
    const cancelDespachoBtn = document.getElementById('cancel-despacho-btn');

    document.body.addEventListener('click', function(e) {
        if (e.target.closest && e.target.closest('.open-despacho-abertura-modal-btn')) {
            if (despachoModal) despachoModal.classList.add('active');
        }
    });

    if (cancelDespachoBtn) {
        cancelDespachoBtn.addEventListener('click', () => {
            despachoModal.classList.remove('active');
        });
    }

    if (despachoModal) {
        despachoModal.addEventListener('click', (e) => {
            if (e.target === despachoModal) {
                despachoModal.classList.remove('active');
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
