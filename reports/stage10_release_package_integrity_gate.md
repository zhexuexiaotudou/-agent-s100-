# stage10_release_package_integrity_gate

verdict: `ok_stage10_release_package_integrity_gate`

- PASS: release manifest exists - 
- PASS: release package ok - []
- PASS: tar package exists - dist/digua-ai-nas-s100p-0.1.0.tar.gz
- PASS: zip package exists - dist/digua-ai-nas-s100p-0.1.0.zip
- PASS: no model weights - {'no_model_weights': True, 'no_private_user_data': True, 'no_secrets': True, 'no_third_party_images': True}
- PASS: no third-party images - {'no_model_weights': True, 'no_private_user_data': True, 'no_secrets': True, 'no_third_party_images': True}
- PASS: no private user data - {'no_model_weights': True, 'no_private_user_data': True, 'no_secrets': True, 'no_third_party_images': True}
- PASS: no secrets - {'no_model_weights': True, 'no_private_user_data': True, 'no_secrets': True, 'no_third_party_images': True}
- PASS: manifest-packaged sample files present - {'ok': True, 'checked_records': 160, 'missing_from_file_list': [], 'missing_from_tar': []}
