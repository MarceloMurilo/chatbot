# 🚀 Como fazer deploy do backend

## Passo a passo para subir no GitHub

### 1. Inicializar Git (se ainda não tiver)

```powershell
# No diretório raiz do projeto (Trilhas-IA)
git init
```

### 2. Adicionar arquivos do backend

```powershell
# Adicionar apenas a pasta modularizado e arquivos de configuração
git add modularizado/
git add .gitignore
git add README.md
```

### 3. Fazer commit

```powershell
git commit -m "Initial commit: Backend GovGlossary"
```

### 4. Conectar ao repositório remoto

```powershell
git remote add origin https://github.com/MarceloMurilo/chatbot.git
git branch -M main
```

### 5. Fazer push

```powershell
git push -u origin main
```

## ⚠️ IMPORTANTE - Antes de fazer push

1. **Verifique se `chave.json` está no .gitignore** ✅ (já está)
2. **Não commite arquivos sensíveis:**
   - `chave.json` (credenciais Google)
   - `.env` (variáveis de ambiente)
   - Arquivos de banco vetorial (já no .gitignore)

## 📝 Após subir no GitHub

1. Vá para o Render.com
2. Conecte o repositório
3. Configure as variáveis de ambiente
4. Deploy automático!

## 🔧 Comandos úteis

```powershell
# Ver o que será commitado
git status

# Ver arquivos ignorados
git status --ignored

# Adicionar todos os arquivos (cuidado!)
git add .

# Ver histórico
git log
```

