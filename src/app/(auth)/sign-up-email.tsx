import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Button } from '@/components/button';
import { AuthPage, authStyles, Field } from '@/components/form';
import { Colors, Fonts, Radius } from '@/constants/theme';
import { useSession, type Role } from '@/lib/session';

const ROLES: { role: Role; title: string; subtitle: string; icon: keyof typeof Ionicons.glyphMap }[] = [
  { role: 'renter', title: 'Rent', subtitle: 'I’m looking for a place', icon: 'search' },
  { role: 'landlord', title: 'Landlord', subtitle: 'I rent out my property', icon: 'key-outline' },
  { role: 'agent', title: 'Agent', subtitle: 'I list for an agency', icon: 'briefcase-outline' },
];

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** 02b · Sign up with email, and choose Renter / Landlord / Agent. */
export default function SignUpEmail() {
  const { signIn } = useSession();
  const [role, setRole] = useState<Role>('renter');
  const [name, setName] = useState('');
  const [agency, setAgency] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const errors = {
    name: name.trim().length < 2 ? 'Enter your full name' : undefined,
    agency: role === 'agent' && !agency.trim() ? 'Enter your agency name' : undefined,
    email: !EMAIL_RE.test(email.trim()) ? 'Enter a valid email address' : undefined,
    password: password.length < 8 ? 'Use at least 8 characters' : undefined,
  };
  const valid = !Object.values(errors).some(Boolean);
  const show = (e?: string) => (submitted ? e : undefined);

  const onSubmit = () => {
    setSubmitted(true);
    if (!valid) return;
    signIn({
      name: name.trim(),
      email: email.trim().toLowerCase(),
      role,
      agencyName: role === 'agent' ? agency.trim() : undefined,
    });
    if (router.canDismiss()) router.dismissAll();
    router.replace('/home');
  };

  return (
    <AuthPage>
      <Text style={authStyles.title}>Sign up with email</Text>
      <Text style={authStyles.subtitle}>What brings you to Rent Me?</Text>

      <View style={styles.roles}>
        {ROLES.map((r) => {
          const active = r.role === role;
          return (
            <Pressable
              key={r.role}
              onPress={() => setRole(r.role)}
              accessibilityRole="radio"
              accessibilityState={{ selected: active }}
              style={[styles.role, active && styles.roleActive]}>
              <Ionicons name={r.icon} size={22} color={active ? Colors.primary : Colors.navy} />
              <Text style={[styles.roleTitle, active && { color: Colors.primary }]}>{r.title}</Text>
              <Text style={styles.roleSub}>{r.subtitle}</Text>
            </Pressable>
          );
        })}
      </View>

      <Field label="Full name" value={name} onChangeText={setName} placeholder="Tebogo Dithobane" autoComplete="name" error={show(errors.name)} />
      {role === 'agent' && (
        <Field label="Agency name" value={agency} onChangeText={setAgency} placeholder="Neo Properties" error={show(errors.agency)} />
      )}
      <Field
        label="Email"
        value={email}
        onChangeText={setEmail}
        placeholder="you@example.com"
        keyboardType="email-address"
        autoCapitalize="none"
        autoComplete="email"
        error={show(errors.email)}
      />
      <Field
        label="Password"
        value={password}
        onChangeText={setPassword}
        placeholder="At least 8 characters"
        secureTextEntry
        autoComplete="new-password"
        error={show(errors.password)}
      />

      <Button title="Create Account" onPress={onSubmit} style={{ marginTop: 8 }} />
    </AuthPage>
  );
}

const styles = StyleSheet.create({
  roles: { flexDirection: 'row', gap: 10, marginBottom: 24 },
  role: {
    flex: 1,
    borderWidth: 1.5,
    borderColor: Colors.border,
    borderRadius: Radius.md,
    padding: 12,
    gap: 4,
  },
  roleActive: { borderColor: Colors.primary, backgroundColor: Colors.chip },
  roleTitle: { fontFamily: Fonts.bold, fontSize: 14, color: Colors.text, marginTop: 4 },
  roleSub: { fontFamily: Fonts.regular, fontSize: 11, lineHeight: 15, color: Colors.textSecondary },
});
