# Publish KnobLooper to GitHub

## 1. Create the repository on GitHub

Create a new empty repository, for example:

- Repository name: `KnobLooper`
- Visibility: Public or Private
- Do **not** initialize it with a README, `.gitignore`, or license if you are uploading this folder as-is

## 2. Open a terminal in the project folder

```bash
cd /path/to/KnobLooper_github_ready
```

## 3. Initialize Git

```bash
git init
git branch -M main
git add .
git commit -m "Initial public alpha"
```

## 4. Connect the GitHub repository

Replace `YOUR-USERNAME` with your GitHub username:

```bash
git remote add origin https://github.com/YOUR-USERNAME/KnobLooper.git
```

## 5. Push the first version

```bash
git push -u origin main
```

## 6. Later updates

```bash
git add .
git commit -m "Describe your changes here"
git push
```

## Suggested first repo description

> Desktop tool for recording MIDI knob gestures and replaying them as OSC loops for live audiovisual performance workflows.

## Suggested topics

- midi
- osc
- python
- pyside6
- live-performance
- madmapper
- audiovisual
- controller
