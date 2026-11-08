import SwiftUI

struct LoginView: View {
    @Environment(AppSession.self) private var session
    @AppStorage("serverURL") private var serverURL = "https://api.example.com"
    @State private var email = ""
    @State private var password = ""
    @State private var name = ""
    @State private var registering = false
    @State private var busy = false
    @State private var error: String?

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    VStack(spacing: 6) {
                        Image(systemName: "doc.text.magnifyingglass").font(.system(size: 48)).foregroundStyle(Theme.gold)
                        Text("Bharati Investigation Desk").font(.title2.bold()).foregroundStyle(Theme.navy)
                        Text("AI-assisted insurance claim investigation").font(.footnote).foregroundStyle(.secondary)
                    }
                    .frame(maxWidth: .infinity).padding(.vertical, 8)
                }
                .listRowBackground(Color.clear)
                Section("Server") {
                    TextField("https://api.your-domain.in", text: $serverURL)
                        .keyboardType(.URL).textInputAutocapitalization(.never).autocorrectionDisabled()
                }
                Section(registering ? "Create account" : "Sign in") {
                    if registering { TextField("Full name", text: $name).textContentType(.name) }
                    TextField("Email", text: $email).keyboardType(.emailAddress)
                        .textInputAutocapitalization(.never).textContentType(.username)
                    SecureField("Password (min 10 characters)", text: $password)
                        .textContentType(registering ? .newPassword : .password)
                }
                ErrorBanner(message: error).listRowBackground(Color.clear)
                Section {
                    Button {
                        Task { await submit() }
                    } label: {
                        HStack { Spacer(); if busy { ProgressView() } else { Text(registering ? "Create account" : "Sign in").bold() }; Spacer() }
                    }
                    .disabled(busy || email.isEmpty || password.count < (registering ? 10 : 1))
                    Button(registering ? "I already have an account" : "First-time setup: create account") {
                        registering.toggle()
                    }.font(.footnote)
                }
            }
        }
    }

    private func submit() async {
        busy = true; error = nil
        defer { busy = false }
        do { try await session.signIn(email: email, password: password, register: registering, name: name) }
        catch { self.error = error.localizedDescription }
    }
}
