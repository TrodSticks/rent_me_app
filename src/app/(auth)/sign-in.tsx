import { router } from 'expo-router';
import { useState } from 'react';
import { Text } from 'react-native';

import { Button } from '@/components/button';
import { AuthPage, authStyles, Field } from '@/components/form';
import { useSession } from '@/lib/session';

/** Sign in with email. Until Supabase is connected any valid-looking login is accepted. */
export default function SignIn() {
  const { signIn } = useSession();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string>();

  const onSubmit = () => {
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()) || !password) {
      setError('Enter your email and password');
      return;
    }
    const name = email.split('@')[0];
    signIn({ name: name.charAt(0).toUpperCase() + name.slice(1), email: email.trim(), role: 'renter' });
    if (router.canDismiss()) router.dismissAll();
    router.replace('/home');
  };

  return (
    <AuthPage>
      <Text style={authStyles.title}>Welcome back</Text>
      <Text style={authStyles.subtitle}>Sign in to see your saved places and messages.</Text>
      <Field
        label="Email"
        value={email}
        onChangeText={setEmail}
        placeholder="you@example.com"
        keyboardType="email-address"
        autoCapitalize="none"
        autoComplete="email"
      />
      <Field
        label="Password"
        value={password}
        onChangeText={setPassword}
        placeholder="Your password"
        secureTextEntry
        autoComplete="current-password"
        error={error}
      />
      <Button title="Sign In" onPress={onSubmit} style={{ marginTop: 8 }} />
      <Text style={authStyles.footer}>
        New to Rent Me?{' '}
        <Text style={authStyles.link} onPress={() => router.replace('/sign-up')}>
          Create an account
        </Text>
      </Text>
    </AuthPage>
  );
}
