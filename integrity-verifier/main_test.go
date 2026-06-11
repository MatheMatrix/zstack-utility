package main

import (
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/hex"
	"encoding/pem"
	"os"
	"path/filepath"
	"testing"
)

func writeFile(t *testing.T, path, content string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
}

// fixture builds a signed manifest over a small tree and writes the PEM public key.
// It returns the install root, manifest path, public key path, and the key's fingerprint.
func fixture(t *testing.T, key *rsa.PrivateKey) (string, string, string) {
	t.Helper()
	root := t.TempDir()
	writeFile(t, filepath.Join(root, "lib/mevoco.jar"), "mevoco-content")
	writeFile(t, filepath.Join(root, "conf/license.xml"), "<beans/>")

	jarSum := sha256.Sum256([]byte("mevoco-content"))
	xmlSum := sha256.Sum256([]byte("<beans/>"))
	manifestJSON := `{"files":[` +
		`{"path":"lib/mevoco.jar","sha256":"` + hex.EncodeToString(jarSum[:]) + `"},` +
		`{"path":"conf/license.xml","sha256":"` + hex.EncodeToString(xmlSum[:]) + `"}` +
		`],"schema_version":1}` + "\n"
	manifestPath := filepath.Join(root, "manifest.json")
	writeFile(t, manifestPath, manifestJSON)

	hashed := sha256.Sum256([]byte(manifestJSON))
	sig, err := rsa.SignPKCS1v15(rand.Reader, key, crypto.SHA256, hashed[:])
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(manifestPath+".sig", sig, 0o644); err != nil {
		t.Fatal(err)
	}

	der, err := x509.MarshalPKIXPublicKey(&key.PublicKey)
	if err != nil {
		t.Fatal(err)
	}
	pubPath := filepath.Join(root, "pub.pem")
	writeFile(t, pubPath, string(pem.EncodeToMemory(&pem.Block{Type: "PUBLIC KEY", Bytes: der})))
	return root, manifestPath, pubPath
}

func fingerprint(t *testing.T, key *rsa.PrivateKey) string {
	t.Helper()
	der, err := x509.MarshalPKIXPublicKey(&key.PublicKey)
	if err != nil {
		t.Fatal(err)
	}
	sum := sha256.Sum256(der)
	return hex.EncodeToString(sum[:])
}

func TestVerifyCleanTree(t *testing.T) {
	key, _ := rsa.GenerateKey(rand.Reader, 2048)
	root, manifestPath, pubPath := fixture(t, key)
	trustedPubKeyFingerprint = fingerprint(t, key)
	defer func() { trustedPubKeyFingerprint = "" }()

	res, err := verify(manifestPath, pubPath, root)
	if err != nil {
		t.Fatal(err)
	}
	if res.Status != "verified" || !res.PubKeyAnchored || len(res.Failures) != 0 {
		t.Fatalf("expected verified+anchored, got %+v", res)
	}
}

func TestVerifyTamperedFile(t *testing.T) {
	key, _ := rsa.GenerateKey(rand.Reader, 2048)
	root, manifestPath, pubPath := fixture(t, key)
	trustedPubKeyFingerprint = fingerprint(t, key)
	defer func() { trustedPubKeyFingerprint = "" }()

	writeFile(t, filepath.Join(root, "lib/mevoco.jar"), "EVIL")
	res, _ := verify(manifestPath, pubPath, root)
	if res.Status != "tampered" || len(res.Failures) != 1 || res.Failures[0].Path != "lib/mevoco.jar" {
		t.Fatalf("expected tampered on mevoco.jar, got %+v", res)
	}
}

func TestRejectSwappedPublicKey(t *testing.T) {
	key, _ := rsa.GenerateKey(rand.Reader, 2048)
	attacker, _ := rsa.GenerateKey(rand.Reader, 2048)
	root, manifestPath, _ := fixture(t, key)

	// Pin the real key, but the attacker re-signs the manifest with their key and drops
	// in their own public key. The fingerprint pin must reject it.
	trustedPubKeyFingerprint = fingerprint(t, key)
	defer func() { trustedPubKeyFingerprint = "" }()

	manifestBytes, _ := os.ReadFile(manifestPath)
	hashed := sha256.Sum256(manifestBytes)
	sig, _ := rsa.SignPKCS1v15(rand.Reader, attacker, crypto.SHA256, hashed[:])
	os.WriteFile(manifestPath+".sig", sig, 0o644)
	der, _ := x509.MarshalPKIXPublicKey(&attacker.PublicKey)
	attackerPub := filepath.Join(root, "attacker_pub.pem")
	os.WriteFile(attackerPub, pem.EncodeToMemory(&pem.Block{Type: "PUBLIC KEY", Bytes: der}), 0o644)

	if _, err := verify(manifestPath, attackerPub, root); err == nil {
		t.Fatal("expected fingerprint-pin rejection, got nil error")
	}
}

func TestRejectBadSignature(t *testing.T) {
	key, _ := rsa.GenerateKey(rand.Reader, 2048)
	root, manifestPath, pubPath := fixture(t, key)
	trustedPubKeyFingerprint = fingerprint(t, key)
	defer func() { trustedPubKeyFingerprint = "" }()

	os.WriteFile(manifestPath+".sig", []byte("garbage-signature"), 0o644)
	res, _ := verify(manifestPath, pubPath, root)
	if res.Status != "signature_invalid" {
		t.Fatalf("expected signature_invalid, got %+v", res)
	}
}

func TestDeveloperBuildReportsNotAnchored(t *testing.T) {
	key, _ := rsa.GenerateKey(rand.Reader, 2048)
	root, manifestPath, pubPath := fixture(t, key)
	trustedPubKeyFingerprint = "" // developer build: no pin

	res, err := verify(manifestPath, pubPath, root)
	if err != nil {
		t.Fatal(err)
	}
	if res.Status != "verified" || res.PubKeyAnchored {
		t.Fatalf("expected verified but not anchored, got %+v", res)
	}
}
