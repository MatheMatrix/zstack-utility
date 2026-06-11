// Command zstack-integrity-verifier is the trust-anchored half of the ZStack license
// hardening integrity check.
//
// It verifies a detached signature over the release manifest using a public key whose
// fingerprint is pinned into this binary at build time, then verifies the SHA-256 of
// every critical file the manifest records. Because the binary is compiled and the
// trusted fingerprint is baked in, replacing the on-disk public key (and re-signing a
// tampered manifest with an attacker key) no longer defeats the check: the attacker must
// also reverse and re-patch this binary and recompute the embedded fingerprint.
//
// This does not make tampering impossible under OS root — ctl.py, which invokes this
// helper, is itself patchable. It raises the cost of forging the manifest from "edit a
// JSON file" to "defeat a pinned, compiled verifier".
//
// trustedPubKeyFingerprint MUST be injected in release builds:
//
//	go build -ldflags "-X main.trustedPubKeyFingerprint=<sha256-hex-of-DER-pubkey>"
//
// When empty (developer build) the public-key pin is skipped and the result is reported
// as not fully anchored.
package main

import (
	"crypto"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/hex"
	"encoding/json"
	"encoding/pem"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
)

var trustedPubKeyFingerprint string

type fileEntry struct {
	Path   string `json:"path"`
	Sha256 string `json:"sha256"`
}

type manifest struct {
	SchemaVersion int         `json:"schema_version"`
	Files         []fileEntry `json:"files"`
}

type failure struct {
	Path   string `json:"path"`
	Reason string `json:"reason"`
}

type result struct {
	Status         string    `json:"status"`
	PubKeyAnchored bool      `json:"pubkey_anchored"`
	Failures       []failure `json:"failures"`
}

func main() {
	manifestPath := flag.String("manifest", "", "path to manifest.json")
	pubKeyPath := flag.String("pubkey", "", "path to release public key (PEM)")
	root := flag.String("root", "", "install root the manifest paths are relative to")
	flag.Parse()

	if *manifestPath == "" || *pubKeyPath == "" || *root == "" {
		fmt.Fprintln(os.Stderr, "usage: zstack-integrity-verifier --manifest M --pubkey K --root R")
		os.Exit(2)
	}

	res, err := verify(*manifestPath, *pubKeyPath, *root)
	if err != nil {
		emit(result{Status: "error", Failures: []failure{{Path: "", Reason: err.Error()}}})
		os.Exit(2)
	}
	emit(res)
	if res.Status != "verified" {
		os.Exit(1)
	}
}

func emit(res result) {
	if res.Failures == nil {
		res.Failures = []failure{}
	}
	out, _ := json.Marshal(res)
	fmt.Println(string(out))
}

func verify(manifestPath, pubKeyPath, root string) (result, error) {
	pub, err := loadPublicKey(pubKeyPath)
	if err != nil {
		return result{}, err
	}

	anchored, err := checkPubKeyPin(pubKeyPath)
	if err != nil {
		return result{}, err
	}

	manifestBytes, err := os.ReadFile(manifestPath)
	if err != nil {
		return result{}, err
	}
	sig, err := os.ReadFile(manifestPath + ".sig")
	if err != nil {
		return result{}, fmt.Errorf("cannot read detached signature: %v", err)
	}

	hashed := sha256.Sum256(manifestBytes)
	if err := rsa.VerifyPKCS1v15(pub, crypto.SHA256, hashed[:], sig); err != nil {
		return result{Status: "signature_invalid", PubKeyAnchored: anchored,
			Failures: []failure{{Path: filepath.Base(manifestPath), Reason: "manifest signature verification failed"}}}, nil
	}

	var m manifest
	if err := json.Unmarshal(manifestBytes, &m); err != nil {
		return result{}, fmt.Errorf("cannot parse manifest: %v", err)
	}

	failures := verifyFiles(root, m)
	status := "verified"
	if len(failures) > 0 {
		status = "tampered"
	}
	return result{Status: status, PubKeyAnchored: anchored, Failures: failures}, nil
}

func loadPublicKey(path string) (*rsa.PublicKey, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	block, _ := pem.Decode(data)
	if block == nil {
		return nil, fmt.Errorf("public key is not valid PEM")
	}
	parsed, err := x509.ParsePKIXPublicKey(block.Bytes)
	if err != nil {
		return nil, err
	}
	pub, ok := parsed.(*rsa.PublicKey)
	if !ok {
		return nil, fmt.Errorf("public key is not RSA")
	}
	return pub, nil
}

// checkPubKeyPin compares the SHA-256 of the DER public key against the fingerprint
// baked into this binary. An empty embedded fingerprint means a developer build with no
// anchor; that is reported (pubkey_anchored=false) rather than silently trusted.
func checkPubKeyPin(path string) (bool, error) {
	if trustedPubKeyFingerprint == "" {
		return false, nil
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return false, err
	}
	block, _ := pem.Decode(data)
	if block == nil {
		return false, fmt.Errorf("public key is not valid PEM")
	}
	sum := sha256.Sum256(block.Bytes)
	if hex.EncodeToString(sum[:]) != trustedPubKeyFingerprint {
		return false, fmt.Errorf("public key fingerprint does not match the pinned release key")
	}
	return true, nil
}

func verifyFiles(root string, m manifest) []failure {
	var failures []failure
	for _, entry := range m.Files {
		if entry.Sha256 == "" {
			continue
		}
		abs := filepath.Join(root, entry.Path)
		actual, err := sha256OfFile(abs)
		if err != nil {
			failures = append(failures, failure{Path: entry.Path, Reason: "missing"})
			continue
		}
		if actual != entry.Sha256 {
			failures = append(failures, failure{Path: entry.Path, Reason: "sha256 mismatch"})
		}
	}
	return failures
}

func sha256OfFile(path string) (string, error) {
	fd, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer fd.Close()
	h := sha256.New()
	if _, err := io.Copy(h, fd); err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}
