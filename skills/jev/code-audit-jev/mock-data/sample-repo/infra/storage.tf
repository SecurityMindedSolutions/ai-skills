# VULN insecure_configuration: public bucket
resource "google_storage_bucket_iam_member" "uploads_public" {
  bucket = google_storage_bucket.uploads.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

# CLEAN: private bucket with uniform access
resource "google_storage_bucket" "uploads" {
  name                        = "acme-uploads"
  location                    = "US"
  uniform_bucket_level_access = true
}

# VULN insecure_configuration: SSH open to the world
resource "google_compute_firewall" "ssh_open" {
  name    = "allow-ssh-anywhere"
  network = "default"
  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
  source_ranges = ["0.0.0.0/0"]
}

# VULN insecure_configuration: project-wide owner for a runtime service account
resource "google_project_iam_member" "worker_owner" {
  project = var.project_id
  role    = "roles/owner"
  member  = "serviceAccount:${google_service_account.worker.email}"
}

# CLEAN: scoped role
resource "google_project_iam_member" "worker_logs" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.worker.email}"
}
